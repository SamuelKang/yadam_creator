#!/usr/bin/env bash
set -u
STORY_ID=${STORY_ID:-story16}
START=${START:-20}
END=${END:-$(jq '.scenes|length' work/${STORY_ID}/out/project.json)}
FLOW_SKIP_CHARACTER_PRECHECK=${FLOW_SKIP_CHARACTER_PRECHECK:-0}
FLOW_USE_PROJECT_REFS=${FLOW_USE_PROJECT_REFS:-0}
FLOW_DELETE_SCENE_CARD_AFTER_SAVE=${FLOW_DELETE_SCENE_CARD_AFTER_SAVE:-1}
FLOW_REGENERATE_ON_NO_MATCH=${FLOW_REGENERATE_ON_NO_MATCH:-1}
RUN_LOG="work/${STORY_ID}/logs/flow_resume_loop_$(date +%s).log"
FLOW_REGENERATE_ON_VERIFY_FAIL=${FLOW_REGENERATE_ON_VERIFY_FAIL:-0}

BATCH_EXTRA_ARGS=()
if [[ "$FLOW_SKIP_CHARACTER_PRECHECK" == "1" ]]; then
  BATCH_EXTRA_ARGS+=(--skip-character-precheck)
fi

echo "RUN_LOG=$RUN_LOG"
echo "FLOW_USE_PROJECT_REFS=$FLOW_USE_PROJECT_REFS" | tee -a "$RUN_LOG"
echo "FLOW_DELETE_SCENE_CARD_AFTER_SAVE=$FLOW_DELETE_SCENE_CARD_AFTER_SAVE" | tee -a "$RUN_LOG"
echo "FLOW_REGENERATE_ON_NO_MATCH=$FLOW_REGENERATE_ON_NO_MATCH" | tee -a "$RUN_LOG"
echo "[INIT] refresh flow page" | tee -a "$RUN_LOG"
PYTHONUNBUFFERED=1 .venv/bin/python skills/flow_scene/scripts/refresh_flow_page.py >> "$RUN_LOG" 2>&1
ref_rc=$?
echo "[INIT] refresh rc=$ref_rc" | tee -a "$RUN_LOG"
if [[ $ref_rc -ne 0 ]]; then
  echo "[INIT] FAILED refresh flow page. stop." | tee -a "$RUN_LOG"
  exit 1
fi
for sid in $(seq ${START} ${END}); do
  png=$(printf "work/${STORY_ID}/clips/%03d.png" "$sid")
  jpg=$(printf "work/${STORY_ID}/clips/%03d.jpg" "$sid")
  if [[ -f "$png" || -f "$jpg" ]]; then
    echo "[SCENE $(printf '%03d' $sid)] skip exists" | tee -a "$RUN_LOG"
    continue
  fi

  echo "[SCENE $(printf '%03d' $sid)] generate start" | tee -a "$RUN_LOG"
  if [[ "$FLOW_USE_PROJECT_REFS" == "1" ]]; then
    PYTHONUNBUFFERED=1 .venv/bin/python skills/flow_scene/scripts/generate_scene_with_project_refs.py \
      --story-id ${STORY_ID} \
      --scene-id $sid \
      --submit-only \
      --gen-poll-sec 10 >> "$RUN_LOG" 2>&1
  else
    PYTHONUNBUFFERED=1 .venv/bin/python scripts/playwright_gemini_cdp_batch.py \
      --story-id ${STORY_ID} \
      --url https://labs.google/fx/tools/flow \
      --start-scene $sid \
      --end-scene $sid \
      --overwrite \
      --gen-poll-sec 1.0 \
      --start-fallback-sec 15 \
      --min-post-submit-sec 25 \
      --timeout-sec 240 \
      --cooldown-sec 2 \
      --idle-timeout-sec 90 \
      --idle-stable-sec 2.0 \
      --idle-poll-sec 0.5 \
      "${BATCH_EXTRA_ARGS[@]}" >> "$RUN_LOG" 2>&1
  fi
  gen_rc=$?
  echo "[SCENE $(printf '%03d' $sid)] generate rc=$gen_rc" | tee -a "$RUN_LOG"
  if [[ $gen_rc -ne 0 ]]; then
    if [[ $gen_rc -eq 9 ]]; then
      echo "[SCENE $(printf '%03d' $sid)] FAILED multi-output detected (delta>1). stop to avoid duplicate images." | tee -a "$RUN_LOG"
    elif [[ $gen_rc -eq 10 ]]; then
      echo "[SCENE $(printf '%03d' $sid)] FAILED output count is not x1 before submit. stop to avoid duplicate images." | tee -a "$RUN_LOG"
    else
      echo "[SCENE $(printf '%03d' $sid)] FAILED generate step rc=$gen_rc. skip verify." | tee -a "$RUN_LOG"
    fi
    exit 1
  fi

  echo "[SCENE $(printf '%03d' $sid)] verify/save start (top1)" | tee -a "$RUN_LOG"
  VERIFY_EXTRA_ARGS=()
  if [[ "$FLOW_DELETE_SCENE_CARD_AFTER_SAVE" == "1" ]]; then
    VERIFY_EXTRA_ARGS+=(--delete-after-save)
  fi
  PYTHONUNBUFFERED=1 .venv/bin/python skills/flow_scene/scripts/verify_scene_reuse_exact.py --story-id ${STORY_ID} --scene-id $sid --top-n 1 --wait-sec 60 --poll-sec 10 "${VERIFY_EXTRA_ARGS[@]}" | tee -a "$RUN_LOG"
  ver_rc=${PIPESTATUS[0]}
  if [[ $ver_rc -ne 0 ]]; then
    echo "[SCENE $(printf '%03d' $sid)] verify top1 failed rc=$ver_rc -> verify-only retry (top3, no regenerate)" | tee -a "$RUN_LOG"
    PYTHONUNBUFFERED=1 .venv/bin/python skills/flow_scene/scripts/verify_scene_reuse_exact.py --story-id ${STORY_ID} --scene-id $sid --top-n 3 --wait-sec 120 --poll-sec 10 "${VERIFY_EXTRA_ARGS[@]}" | tee -a "$RUN_LOG"
    ver_rc2=${PIPESTATUS[0]}
    if [[ $ver_rc2 -ne 0 ]]; then
      if [[ $ver_rc2 -eq 3 && "$FLOW_REGENERATE_ON_NO_MATCH" == "1" ]]; then
        echo "[SCENE $(printf '%03d' $sid)] no_exact_match after verify-only retry -> regenerate once" | tee -a "$RUN_LOG"
        if [[ "$FLOW_USE_PROJECT_REFS" == "1" ]]; then
          PYTHONUNBUFFERED=1 .venv/bin/python skills/flow_scene/scripts/generate_scene_with_project_refs.py \
            --story-id ${STORY_ID} \
            --scene-id $sid \
            --submit-only \
            --gen-poll-sec 10 >> "$RUN_LOG" 2>&1
        else
          PYTHONUNBUFFERED=1 .venv/bin/python scripts/playwright_gemini_cdp_batch.py \
            --story-id ${STORY_ID} \
            --url https://labs.google/fx/tools/flow \
            --start-scene $sid \
            --end-scene $sid \
            --overwrite \
            --gen-poll-sec 1.0 \
            --start-fallback-sec 15 \
            --min-post-submit-sec 25 \
            --timeout-sec 240 \
            --cooldown-sec 2 \
            --idle-timeout-sec 90 \
            --idle-stable-sec 2.0 \
            --idle-poll-sec 0.5 \
            "${BATCH_EXTRA_ARGS[@]}" >> "$RUN_LOG" 2>&1
        fi
        gen2_rc=$?
        echo "[SCENE $(printf '%03d' $sid)] regenerate-on-no-match rc=$gen2_rc" | tee -a "$RUN_LOG"
        if [[ $gen2_rc -ne 0 ]]; then
          echo "[SCENE $(printf '%03d' $sid)] FAILED regenerate-on-no-match rc=$gen2_rc" | tee -a "$RUN_LOG"
          exit 1
        fi
        PYTHONUNBUFFERED=1 .venv/bin/python skills/flow_scene/scripts/verify_scene_reuse_exact.py --story-id ${STORY_ID} --scene-id $sid --top-n 3 --wait-sec 120 --poll-sec 10 "${VERIFY_EXTRA_ARGS[@]}" | tee -a "$RUN_LOG"
        ver_rc4=${PIPESTATUS[0]}
        if [[ $ver_rc4 -ne 0 ]]; then
          echo "[SCENE $(printf '%03d' $sid)] FAILED verify after regenerate-on-no-match rc=$ver_rc4" | tee -a "$RUN_LOG"
          exit 1
        fi
        continue
      fi
      if [[ "$FLOW_REGENERATE_ON_VERIFY_FAIL" == "1" ]]; then
        echo "[SCENE $(printf '%03d' $sid)] verify retry failed rc=$ver_rc2 -> regenerate once (opt-in)" | tee -a "$RUN_LOG"
        if [[ "$FLOW_USE_PROJECT_REFS" == "1" ]]; then
          PYTHONUNBUFFERED=1 .venv/bin/python skills/flow_scene/scripts/generate_scene_with_project_refs.py \
            --story-id ${STORY_ID} \
            --scene-id $sid \
            --submit-only \
            --gen-poll-sec 10 >> "$RUN_LOG" 2>&1
        else
          PYTHONUNBUFFERED=1 .venv/bin/python scripts/playwright_gemini_cdp_batch.py \
            --story-id ${STORY_ID} \
            --url https://labs.google/fx/tools/flow \
            --start-scene $sid \
            --end-scene $sid \
            --overwrite \
            --gen-poll-sec 1.0 \
            --start-fallback-sec 15 \
            --min-post-submit-sec 25 \
            --timeout-sec 240 \
            --cooldown-sec 2 \
            --idle-timeout-sec 90 \
            --idle-stable-sec 2.0 \
            --idle-poll-sec 0.5 \
            "${BATCH_EXTRA_ARGS[@]}" >> "$RUN_LOG" 2>&1
        fi
        echo "[SCENE $(printf '%03d' $sid)] final verify after regen (top3)" | tee -a "$RUN_LOG"
        PYTHONUNBUFFERED=1 .venv/bin/python skills/flow_scene/scripts/verify_scene_reuse_exact.py --story-id ${STORY_ID} --scene-id $sid --top-n 3 --wait-sec 120 --poll-sec 10 "${VERIFY_EXTRA_ARGS[@]}" | tee -a "$RUN_LOG"
        ver_rc3=${PIPESTATUS[0]}
        if [[ $ver_rc3 -ne 0 ]]; then
          echo "[SCENE $(printf '%03d' $sid)] FAILED final verify rc=$ver_rc3" | tee -a "$RUN_LOG"
          exit 1
        fi
      else
        echo "[SCENE $(printf '%03d' $sid)] FAILED verify retry rc=$ver_rc2 (no auto-regenerate; set FLOW_REGENERATE_ON_VERIFY_FAIL=1 to enable)" | tee -a "$RUN_LOG"
        exit 1
      fi
    fi
  fi
  echo "[SCENE $(printf '%03d' $sid)] done" | tee -a "$RUN_LOG"

done

echo "ALL_DONE story=${STORY_ID} start=${START} end=${END}" | tee -a "$RUN_LOG"
