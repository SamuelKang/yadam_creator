# scene별 대본-이미지 프롬프트 검수

기준: 대본의 등장인물, 장소, 시간대, 사건성, 분위기가 llm_clip_prompt에 실제로 반영되었는지 점검.

- 총 scene: 147

- 적합: 24

- 부분수정: 45

- 불일치: 78


## 추가 검수: 지브리 스타일 반영도

판정:

- 문구 반영: 있음
- 스타일 일관성: 부족
- 최종 평: 부분 반영

### 판단 근거

1. scene 프롬프트 본문에는 `hand-drawn Ghibli-inspired animation` 같은 표현이 반복적으로 들어가 있어, 지브리풍을 유도하려는 의도 자체는 분명히 존재한다.
2. 그러나 같은 프롬프트 안의 안전/스타일 제약에는 `Keep a stylized 2D Korean manhwa/webtoon look`가 함께 들어가 있어, 지브리풍과 한국 웹툰풍이 동시에 지시되는 충돌 구조가 있다.
3. 프로젝트 레벨의 `style_profile` 자체가 `k_webtoon`으로 설정되어 있어, 파이프라인의 기본 화풍은 지브리 단일 화풍이 아니라 한국 웹툰 베이스에 더 가깝다.
4. 따라서 현재 프롬프트 세트는 "지브리 스타일 요청이 문구상 일부 반영된 상태"이지, "지브리 스타일이 일관되게 보장되도록 정리된 상태"로 보기는 어렵다.

### 실무 판단

- 현재 상태는 **지브리풍 참고 + 한국 웹툰풍 본체**에 가깝다.
- 실제 출력도 지브리 단일 화풍보다는, **지브리 느낌이 일부 섞인 웹툰풍**으로 나올 가능성이 높다.
- 정량적으로 표현하면 대략 **지브리 4 / 10, 웹툰 6 / 10** 정도의 혼합 상태로 평가할 수 있다.

### 수정 권고

1. 지브리 스타일을 우선 목표로 할 경우, scene 프롬프트와 안전 제약에서 `Korean manhwa/webtoon look` 계열 문구를 제거하거나 후순위로 낮춰야 한다.
2. 프로젝트의 `style_profile`도 `k_webtoon` 중심 구조를 유지할지 재검토해야 한다.
3. 지브리풍을 유지하려면 scene별 문맥 정확도 보정과 함께, 화풍 지시 역시 한 방향으로 통일해야 한다.


## Scene 1 — 불일치

- 챕터: 서리 내린 산골의 침묵

- 대본 요약: 서슬 퍼런 초겨울 서리가 경상도 고치마을의 마른 논바닥을 하얗게 뒤덮습니다. 영조 대왕이 치세하던 그 시절, 영남 땅을 휩쓴 유례없는 흉년은 산골 마을의 숨통마저 조여 오고 있었습니다. 들판에는 이삭 하나 남지 않았

- 프롬프트 요약: Wide shot at a famine-stricken Joseon village field and alley. hungry villagers. faces show grief and panic in the eyes and jaw. Clear facia

- 판단 근거:

  - 무인물 scene인데 프롬프트에 인물군이 들어감

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 2 — 불일치

- 챕터: 서리 내린 산골의 침묵

- 대본 요약: "나라에서 구휼미를 풀었다는 소문만 무성할 뿐, 이 깊은 산골까지 쌀독 채울 곡식이 언제 당도하겠느냐." 마을 사람들은 서로의 눈을 피하며 힘없이 중얼거립니다. 굶주림에 지친 아이들은 울음소리마저 잦아들었고, 길가에

- 프롬프트 요약: Medium shot at a famine-stricken Joseon village field and alley. hungry villagers. faces show grief and panic in the eyes and jaw. Clear fac

- 판단 근거:

  - 무인물 scene인데 프롬프트에 인물군이 들어감

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 3 — 불일치

- 챕터: 서리 내린 산골의 침묵

- 대본 요약: 인심은 곳간에서 난다 하였거늘, 비어버린 곳간만큼이나 사람들의 마음도 가뭄 든 논바닥처럼 갈라져 버렸습니다. 마을 장정 하나가 힘겹게 마른침을 삼키며 퀭한 눈으로 산등성이를 바라봅니다. "이러다간 산사람이 죽은 사람

- 프롬프트 요약: Tight two-shot at burned granary ruins with ash and broken beams. hungry villagers. the burned granary ruins remain clearly visible. Clear f

- 판단 근거:

  - 무인물 scene인데 프롬프트에 인물군이 들어감

  - 화염/소실 연출이 대본 근거보다 과함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 4 — 불일치

- 챕터: 서리 내린 산골의 침묵

- 대본 요약: 그의 말에 곁에 있던 노인이 마른 입술을 떼며 대꾸합니다. "인륜이 다 무엇인가. 내 배가 고프니 자식 입에 들어가는 것도 아까워지는 게 이 흉년일세. 참으로 무서운 세상이야." 산골의 공기는 차갑다 못해 날카롭게 

- 프롬프트 요약: Over-shoulder shot at a famine-stricken Joseon village field and alley. hungry villagers. tension builds through wary glances and guarded po

- 판단 근거:

  - 무인물 scene인데 프롬프트에 인물군이 들어감

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 5 — 불일치

- 챕터: 서리 내린 산골의 침묵

- 대본 요약: 정적만이 감도는 마을에는 이따금 까마귀 울음소리만 들려올 뿐, 생명의 온기라곤 찾아볼 수 없습니다. 먹을 것이 없어 소나무 껍질을 벗겨 먹고 흙을 파먹는 지경에 이르자, 사람들의 눈빛에는 생기 대신 독기만이 서서히 

- 프롬프트 요약: Low-angle medium shot at a famine-stricken Joseon village field and alley. hungry villagers. faces show grief and panic in the eyes and jaw.

- 판단 근거:

  - 무인물 scene인데 프롬프트에 인물군이 들어감

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 6 — 부분수정

- 챕터: 서리 내린 산골의 침묵

- 대본 요약: 이 비극적인 침묵 속에서, 고치마을의 가장 외진 곳에 자리한 판수의 초가집만이 낮게 엎드린 채 폭풍 전야 같은 긴장감을 머금고 있습니다. 서리 맞은 마당 위로 차가운 바람이 휘몰아치며, 곧 닥쳐올 거대한 폭풍을 예고

- 프롬프트 요약: Close-up at a cold dirt courtyard in front of a Joseon thatched house. an elderly father-in-law grips a hoe and pauses in exhausted tension.

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 7 — 부분수정

- 챕터: 고집불통 늙은 농부, 판수

- 대본 요약: 마을 외곽, 무너져가는 울타리 너머로 굽은 등의 노인이 보입니다. 이름은 판수. 평생을 흙과 씨름하며 살아온 이 땅의 상민입니다. 그의 손등은 가뭄 든 논바닥보다

- 프롬프트 요약: Tracking medium shot at a famine-stricken Joseon village field and alley. an exhausted elderly farmer. faces show grief and panic in the eye

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 8 — 부분수정

- 챕터: 고집불통 늙은 농부, 판수

- 대본 요약: 더 깊게 갈라져 있고, 손톱 밑에는 씻어도 지워지지 않는 흙때가 훈장처럼 박혀 있습니다. "에잇, 이놈의 땅덩어리. 죽은 자식 놈처럼 입만 벌리고 있구나." 판수가 마른 논에 괭이를 내리치며 거칠게 숨을 몰아쉽니다.

- 프롬프트 요약: High-angle wide shot at a famine-stricken Joseon village field and alley. an exhausted elderly farmer. tension builds through wary glances a

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 9 — 부분수정

- 챕터: 고집불통 늙은 농부, 판수

- 대본 요약: 마을 사람들은 그를 '독종'이라 부르며 멀리합니다. 아들을 잃고도 눈물 한 방울 보이지 않고, 그저 묵묵히 괭이질만 해대는 그 기이한 고집 때문입니다. 마침 길을 지나던 동네 장정이 혀를 차며 말을 건넵니다. "판수

- 프롬프트 요약: Wide shot at a famine-stricken Joseon village field and alley. an exhausted elderly farmer. faces show grief and panic in the eyes and jaw. 

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 10 — 부분수정

- 챕터: 고집불통 늙은 농부, 판수

- 대본 요약: 판수는 대꾸도 없이 허리를 펴고 장정을 쏘아봅니다. 깊게 패인 주름 사이로 번뜩이는 형형한 눈빛에 장정은 움찔하며 뒷걸음질을 칩니다. "내 땅 내가 파는데 자네가 웬 참견인가. 가서 자네 식구들 거둘 궁리나 하게."

- 프롬프트 요약: Medium shot at a famine-stricken Joseon village field and alley. an exhausted elderly farmer. tension builds through wary glances and guarde

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 11 — 부분수정

- 챕터: 고집불통 늙은 농부, 판수

- 대본 요약: 그는 누구에게도 속내를 내비치지 않습니다. 홀로 남은 며느리와의 생계가 막막할 텐데도, 구걸 한 번 하는 법이 없습니다. 오히려 마을 사람들이 다가오면 가시 돋친 말로 밀어내기 일쑤입니다. 집으로 돌아온 판수가 툇마

- 프롬프트 요약: Tight two-shot at a dim Joseon thatched-house interior. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a 

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 12 — 적합

- 챕터: 고집불통 늙은 농부, 판수

- 대본 요약: 마디마디가 불거진 그 손은 이미 사람의 것이라기보다 고목의 뿌리에 가깝습니다. "살아야지. 죽은 놈은 죽은 놈이고, 산 사람은 어떻게든 줄기를 뻗어야 하는 법이다." 노인은 품 안에서 낡은 수건을 꺼내 얼굴의 땀을 

- 프롬프트 요약: Over-shoulder shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law kee

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 13 — 부분수정

- 챕터: 고집불통 늙은 농부, 판수

- 대본 요약: 그의 눈은 집 한구석, 낡은 빗장이 걸린 작은 곡간을 향해 있습니다. 그 눈빛에는 고집스러운 생존의 의지와 함께, 누구에게도 들켜서는 안 될 무거운 비밀이 서려 있습니다. 서리 내린 산골의 찬바람이 다시금 그의 굽은

- 프롬프트 요약: Low-angle medium shot at a dim Joseon thatched-house interior. an elderly father-in-law. Subtle emotional tension is shown through lowered s

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 14 — 불일치

- 챕터: 무너져가는 초가집의 인물들

- 대본 요약: 삭풍이 몰아치는 판수의 초가 마당에 정갈하게 빗질한 자국이 남았습니다. 그 끝에는 몰락한 양반가의 여식이었으나 이제는 빈농의 며느리가 된 수련이 서 있습니다. 그녀는 해진 무명옷을 입었어도 곧은 등술과 맑은 눈빛만큼

- 프롬프트 요약: Close-up at a dim Joseon thatched-house interior. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a restra

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 15 — 불일치

- 챕터: 무너져가는 초가집의 인물들

- 대본 요약: "아버님, 세숫물 떠놓았습니다. 속이 허하실 텐데 미음이라도 조금 드시지요." 수련이 고운 목소리로 판수를 부릅니다. 남편을 역병으로 잃고 친정으로 돌아갈 법도 하건만, 그녀는 홀로 남은 시아버지를 봉양하며 가문을 

- 프롬프트 요약: Tracking medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law k

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 16 — 불일치

- 챕터: 무너져가는 초가집의 인물들

- 대본 요약: 판수는 그런 며느리를 물끄러미 바라보다 퉁명스럽게 뱉습니다. "내 먹을 것은 걱정 말거라. 네 몸이나 건사해. 얼굴이 반쪽이 되었구나." 판수의 거친 말투에도 수련은 그저 엷게 미소 지으며 고개를 숙입니다.

- 프롬프트 요약: High-angle wide shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law k

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 17 — 부분수정

- 챕터: 무너져가는 초가집의 인물들

- 대본 요약: 하지만 평화는 오래가지 않습니다. 사은기 도는 웃음을 흘리며 사은문을 밀고 들어오는 사내가 있으니, 바로 마을 이장 최 씨입니다. "여보게, 판수 영감! 안에 있는가? 허허, 수련 아범이 가고 나니 집안 꼴이 말이 

- 프롬프트 요약: Wide shot at a famine-stricken Joseon village lane. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head; the dau

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 18 — 부분수정

- 챕터: 무너져가는 초가집의 인물들

- 대본 요약: 최 씨는 기름기 흐르는 얼굴로 마당을 휘둘러보더니, 빨래를 널던 수련의 뒷모습에 음흉한 시선을 던집니다. 판수가 지팡이를 짚고 일어나 앞을 가로막습니다. "이장 어른이 여긴 웬일이시오? 빌려 간 곡식 이자는 다음 달

- 프롬프트 요약: Medium shot at a cold courtyard in front of a thatched house. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village hea

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 19 — 불일치

- 챕터: 무너져가는 초가집의 인물들

- 대본 요약: "에이, 이 사람아. 이자가 문제인가? 내 자네 사정이 딱해서 왔네. 수련이 같은 꽃 같은 아이를 이런 흙구덩이에서 썩힐 셈인가? 내 집 첩실로 보내면 자네 빚도 탕감해주고 쌀독도 가득 채워줌세." 최 씨의 노골적인

- 프롬프트 요약: Tight two-shot at a dim Joseon thatched-house interior. a widowed daughter-in-law and a corrupt village head. Emotional intent is conveyed t

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 20 — 불일치

- 챕터: 무너져가는 초가집의 인물들

- 대본 요약: 판수의 눈에 순식간에 살기가 서립니다. "썩 물러가시오! 내 자식 같은 아이를 쌀 몇 가마에 팔 줄 아는가!" 최 씨는 혀를 차며 대문을 나섭니다. "고집 피우다간 둘 다 굶어 죽을 걸세. 내 곧 다시 오지."

- 프롬프트 요약: Over-shoulder shot at a cold courtyard in front of a thatched house. an elderly father-in-law and a corrupt village head. Rising anger is ca

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 21 — 불일치

- 챕터: 무너져가는 초가집의 인물들

- 대본 요약: 최 씨가 사라진 뒤, 어둠이 깔린 마당 구석에서 그림자 하나가 툭 튀어 나옵니다. 전국 팔도를 떠도는 방물장수 점복이입니다. 그는 판수의 곁으로 다가와 목소리를 낮춥니다. "영감님, 조심하쇼. 최 씨 저놈이 관아 놈

- 프롬프트 요약: Low-angle medium shot at a Joseon county office courtyard. an elderly father-in-law, a corrupt village head, and a nervous informant. Emotio

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 22 — 불일치

- 챕터: 무너져가는 초가집의 인물들

- 대본 요약: 판수는 점복이가 건넨 말을 곱씹으며 말없이 어두운 곡간 쪽을 응시합니다. 수련의 가냘픈 그림자가 문창살에 비치고, 판수의 가슴 속에는 이 거친 세파로부터 며느리를 지켜내야 한다는 무거운 결심이 차오릅니다.

- 프롬프트 요약: Close-up at a famine-stricken Joseon village lane. an elderly father-in-law, a widowed daughter-in-law, and a nervous informant; the daughte

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 23 — 부분수정

- 챕터: 곳간에서 들리는 기이한 소리

- 대본 요약: 마을에 어둠이 깔리고 사위가 적막에 잠기면, 판수의 기이한 행보가 시작됩니다. 노인은 매일 새벽, 남들이 단잠에 빠져 있을 시각에 조용히 일어나 낡은 곳간으로 향합니다. 녹슨 빗장이 '끼이익' 비명을 지르며 열리면,

- 프롬프트 요약: Tracking medium shot at a famine-stricken Joseon village lane. an elderly father-in-law. Emotional intent is conveyed through gaze, posture,

- 판단 근거:

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 24 — 부분수정

- 챕터: 곳간에서 들리는 기이한 소리

- 대본 요약: "아버님, 아직 주무실 시간인데 어딜 가시옵니까?" 방 안에서 기척을 느낀 수련이 조심스레 물어도 판수의 대답은 서늘하기만 합니다. "상관 말고 잠이나 자거라. 곳간 근처엔 얼씬도 하지 마라. 만약 내 말을 어기면 

- 프롬프트 요약: High-angle wide shot at a dim Joseon thatched-house interior. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law ke

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 25 — 부분수정

- 챕터: 곳간에서 들리는 기이한 소리

- 대본 요약: 평소 엄격하긴 했으나 이토록 서슬 퍼런 호통은 처음이었습니다. 수련은 문고리를 잡았던 손을 파르르 떨며 물러납니다. 하지만 담장 너머로 흘러나온 소문은 이미 마을을 뒤덮고 있었습니다. "글쎄, 판수 영감이 밤마다 곳

- 프롬프트 요약: Wide shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law. Rising anger is carried by sharp

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 26 — 부분수정

- 챕터: 곳간에서 들리는 기이한 소리

- 대본 요약: "죽은 아들 놈 혼령을 거기 가둬놓고 밥을 준다는 말도 있고, 귀신을 홀려 곡식을 만들어낸다는 소리도 있어." 마을 사람들의 수군거림은 흉흉한 흉년의 민심을 타고 겉잡을 수 없이 퍼져나갑니다. 수련의 불안감도 극에 

- 프롬프트 요약: Medium shot at a famine-stricken Joseon village lane. a widowed daughter-in-law. A key evidence fragment is raised and inspected with focuse

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 27 — 부분수정

- 챕터: 곳간에서 들리는 기이한 소리

- 대본 요약: 시아버지는 밤마다 산으로 올라가 이름 모를 풀뿌리를 캐오고, 때로는 짐승의 피가 묻은 사발을 들고 곳간으로 들어갔습니다. 어느 깊은 밤, 궁금증을 참지 못한 수련이 곳간 벽에 귀를 가져다 댑니다.

- 프롬프트 요약: Tight two-shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 28 — 적합

- 챕터: 곳간에서 들리는 기이한 소리

- 대본 요약: "…조금만 더 참거라. 곧 날이 밝으면 살 길이 열릴 게야." 안에서 들려오는 판수의 낮은 흐느낌과 함께, 무언가 '스르륵' 하며 바닥을 긁는 기괴한 소리가 들려옵니다. 수련은 소스라치게 놀라 입을 틀어막습니다. 그

- 프롬프트 요약: Over-shoulder shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law kee

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 29 — 부분수정

- 챕터: 곳간에서 들리는 기이한 소리

- 대본 요약: 판수가 곳간 문을 열고 나오자, 수련은 황급히 어둠 속으로 몸을 숨깁니다. 달빛에 비친 판수의 얼굴은 며칠 새 십 년은 늙어버린 듯 초췌했으나, 눈빛만큼은 무서울 정도로 번뜩이고 있었습니다. 노인의 손에 들린 빈 사

- 프롬프트 요약: Low-angle medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law 

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 30 — 불일치

- 챕터: 마을의 위협과 판수의 결단

- 대본 요약: 동이 채 트기도 전, 정적을 깨는 거친 발소리가 판수의 마당을 유린합니다. 이장 최 씨가 관아의 잔챙이들과 건장한 장정 셋을 대동하고 들이닥친 것입니다. 그들의 손에는 몽둥이와 밧줄이 들려 있었습니다. "판수 영감!

- 프롬프트 요약: Close-up at a Joseon county office courtyard. an elderly father-in-law and a corrupt village head. Emotional intent is conveyed through gaze

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 31 — 적합

- 챕터: 마을의 위협과 판수의 결단

- 대본 요약: 최 씨의 고함에 수련이 질겁하며 방에서 뛰어나옵니다. 최 씨는 기다렸다는 듯 수련의 손목을 덥석 낚아챕니다. "옳거니, 이 불쌍한 것. 미친 시아버지 밑에서 고생이 많았지? 오늘 네 시아버지는 관아로 끌려갈 터이니,

- 프롬프트 요약: Tracking medium shot at a Joseon county office courtyard. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head; t

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 32 — 부분수정

- 챕터: 마을의 위협과 판수의 결단

- 대본 요약: "이거 놓으십시오! 아버님! 아버님!" 수련의 비명에 곳간 문이 거칠게 열리며 판수가 튀어나옵니다. 그의 눈은 핏발이 서 있고, 손에는 이가 빠진 낡은 작대기가 들려 있었습니다. 판수는 짐승 같은 포효를 내지르며 최

- 프롬프트 요약: High-angle wide shot at a famine-stricken Joseon village lane. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village he

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 33 — 부분수정

- 챕터: 마을의 위협과 판수의 결단

- 대본 요약: "내 집 마당에서 손을 떼지 못할까! 이 천하의 잡놈들아!" 판수가 휘두르는 작대기가 허공을 가르며 장정의 어깨를 강타합니다. 평소 굽어 있던 등은 간데없고, 광기에 서린 노인의 기세에 장정들이 주춤하며 물러섭니다.

- 프롬프트 요약: Wide shot at a cold courtyard in front of a thatched house. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head;

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 34 — 불일치

- 챕터: 마을의 위협과 판수의 결단

- 대본 요약: "이, 이 영감이 정말 돌았구먼! 여보게들, 저 미치광이를 보게! 저놈이 아들 귀신에 홀려 사람을 잡으려 들어!" 최 씨는 마을 사람들을 향해 소리를 지르며 판수를 '실성한 노인'으로 몰아세웁니다. 마을 사람들은 판

- 프롬프트 요약: Medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a corrupt village head. Subtle emotional tension is shown

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 35 — 불일치

- 챕터: 마을의 위협과 판수의 결단

- 대본 요약: 겨우 침입자들을 쫓아낸 판수는 가쁜 숨을 몰아쉬며 바닥에 주저앉습니다. 수련이 울먹이며 다가와 그의 소매를 붙잡습니다. "아버님, 저 때문에… 저 때문에 아버님이 이런 수모를 당하시니 제가 죽어 마땅합니다." 판수는

- 프롬프트 요약: Tight two-shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law. Urgent movement and pursuit

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 36 — 불일치

- 챕터: 마을의 위협과 판수의 결단

- 대본 요약: 그의 눈에 서렸던 살기는 가시고, 대신 깊고 무거운 결단이 자리 잡습니다. 이대로는 수련을 지킬 수 없음을, 저들의 탐욕이 이 울타리를 완전히 무너뜨릴 것임을 직감한 것입니다. "수련아, 울지 마라. 이 아비가 미치

- 프롬프트 요약: Over-shoulder shot at a cold courtyard in front of a thatched house. a widowed daughter-in-law. Urgent movement and pursuit shape the frame 

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 37 — 불일치

- 챕터: 마을의 위협과 판수의 결단

- 대본 요약: 판수는 떨리는 손으로 수련의 어깨를 꽉 쥡니다. 그의 시선은 다시금 굳게 닫힌 곳간을 향합니다. 이제는 숨기는 것만으로는 부족했습니다. 마을 전체를 속여야만 며느리를 지킬 수 있는, 노부의 처절한 연극이 시작되려 하

- 프롬프트 요약: Low-angle medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law 

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 38 — 적합

- 챕터: 곡간의 빗장을 지르다

- 대본 요약: 최 씨 일당이 물러간 뒤에도 마을의 웅성거림은 가라앉지 않았습니다. 판수는 마당 한가운데 서서 며느리 수련을 빤히 바라보았습니다. 최 씨의 탐욕스러운 눈빛과 마을 사람들의 차가운 시선을 떠올린 판수의 입술이 파르르 

- 프롬프트 요약: Close-up at a dim Joseon thatched-house interior. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head; the daugh

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 39 — 적합

- 챕터: 곡간의 빗장을 지르다

- 대본 요약: "수련아, 내 방으로 들어가서 봇짐을 싸거라. 가장 아끼는 옷 한 벌과 네 시집올 때 가져온 서책만 챙겨라." 수련은 영문을 몰라 눈을 크게 떴습니다. "아버님, 설마 저를 내쫓으려는 것이옵니까? 제가 부족하여 이런

- 프롬프트 요약: Tracking medium shot at a dim Joseon thatched-house interior. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law ke

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 40 — 부분수정

- 챕터: 곡간의 빗장을 지르다

- 대본 요약: "아니다. 너를 살리려는 게다. 저놈들은 굶주린 늑대와 같아서 조만간 이 울타리를 부수고 들어올 게야. 그때는 이 아비도 막지 못한다." 판수는 수련을 이끌고 아무도 발을 들이지 못하게 했던 곡간으로 향했습니다. 육

- 프롬프트 요약: High-angle wide shot at a cold courtyard in front of a thatched house. an elderly father-in-law and a widowed daughter-in-law; the daughter-

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 41 — 불일치

- 챕터: 곡간의 빗장을 지르다

- 대본 요약: 곡간 구석, 볏짚더미를 치우자 성인 한 명이 겨우 들어갈 법한 비밀스러운 틈바구니가 나타났습니다. 판수가 미리 파놓은 지하 토굴과 연결된 공간이었습니다. "여기에 숨어 있거라. 내가 부르기 전까지는 숨소리조차 내지 

- 프롬프트 요약: Wide shot at a famine-stricken Joseon village lane. an elderly father-in-law. Emotional intent is conveyed through gaze, posture, and purpos

- 판단 근거:

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 비밀 통로/토굴 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 42 — 부분수정

- 챕터: 곡간의 빗장을 지르다

- 대본 요약: 수련을 안쪽 깊숙이 밀어 넣은 판수는 다시 곡간 밖으로 나와 대못을 박듯 빗장을 질렀습니다. 그리고는 갑자기 마당 한복판에서 미친 듯이 웃어대기 시작했습니다. "하하하! 내 아들이 돌아왔다! 보아라, 곡간 안에서 내

- 프롬프트 요약: Medium shot at a cold courtyard in front of a thatched house. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law ke

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 43 — 부분수정

- 챕터: 곡간의 빗장을 지르다

- 대본 요약: 담장 너머로 훔쳐보던 마을 사람들이 소스라치게 놀라 뒤로 물러섰습니다. 판수는 헝클어진 머리칼을 휘날리며 곳간 문을 두드리고 덩실덩실 춤을 추었습니다. "오냐, 아들아! 배가 고프냐? 이 아비가 곧 밥을 넣어주마! 

- 프롬프트 요약: Tight two-shot at a famine-stricken Joseon village lane. an elderly father-in-law. Blade threat is visible with tense defensive spacing and 

- 판단 근거:

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 44 — 부분수정

- 챕터: 곡간의 빗장을 지르다

- 대본 요약: 광기에 찬 판수의 외침이 고치마을의 밤공기를 찢어발겼습니다. 사람들은 이제 판수가 완전히 실성했다고 믿으며 뒷걸음질 쳤습니다. "저 집구석엔 귀신이 들었어. 아들 혼령이 곡간을 차지한 게 분명해!" 어두운 곡간 안,

- 프롬프트 요약: Over-shoulder shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law kee

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 45 — 부분수정

- 챕터: 곡간의 빗장을 지르다

- 대본 요약: 자신을 지키기 위해 기꺼이 미치광이가 되기로 한 노부의 결단이, 차가운 곡간 바닥보다 더 시리게 가슴을 파고들었습니다.

- 프롬프트 요약: Low-angle medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law 

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 46 — 부분수정

- 챕터: 어둠 속의 그림자, 산신의 사자

- 대본 요약: 곡간의 두꺼운 널문 사이로 스며드는 달빛은 가느다란 실금 같았습니다. 숨죽여 흐느끼던 수련은 문득 콧전을 스치는 기이한 향기에 고개를 들었습니다. 그것은 산중의 짙은 이끼 냄새 같기도 하고, 오래된 고목이 썩어가는 

- 프롬프트 요약: Close-up at a famine-stricken Joseon village lane. a widowed daughter-in-law. Grief is readable in trembling posture, wet eyes, and restrain

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 47 — 부분수정

- 챕터: 어둠 속의 그림자, 산신의 사자

- 대본 요약: "아버님… 아버님입니까?" 수련이 모기만 한 목소리로 물었으나 밖에서는 판수의 광기 어린 노랫가락만 멀리서 들려올 뿐이었습니다. 그때였습니다. 어둠뿐이어야 할 곡간 구석에서 스르륵, 무언가 움직이는 기척이 났습니다.

- 프롬프트 요약: Tracking medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law k

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 48 — 적합

- 챕터: 어둠 속의 그림자, 산신의 사자

- 대본 요약: 수련의 심장이 멎을 듯 요동쳤습니다. 먼지 쌓인 가마니 너머로 서서히 형체가 드러났습니다. 그것은 사람의 형상을 하고 있었으나, 머리칼은 눈부시게 하얬고 피부는 마치 나무껍질처럼 거칠었습니다. 백발 노인의 환영 같기

- 프롬프트 요약: High-angle wide shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law. Emotional intent is c

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 49 — 적합

- 챕터: 어둠 속의 그림자, 산신의 사자

- 대본 요약: "두려워 말거라. 네 시아버지가 정성으로 바친 것이 내 허기를 채웠으니." 노인의 목소리는 바람이 갈대숲을 훑고 지나가는 듯 서늘했습니다. 수련은 판수가 밤마다 산을 오르내리며 가져온 이름 모를 풀뿌리와 짐승의 피가

- 프롬프트 요약: Wide shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a rest

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 50 — 부분수정

- 챕터: 어둠 속의 그림자, 산신의 사자

- 대본 요약: 그것은 아들의 혼령을 부르는 주술이 아니었습니다. 며느리를 숨겨줄 이 기이한 존재, 산신의 사자에게 바치는 처절한 제물이었습니다. "아버님께서… 저를 위해 산신께 몸을 굽히신 것이옵니까?" 백발의 노인은 대답 대신 

- 프롬프트 요약: Medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a re

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 51 — 부분수정

- 챕터: 어둠 속의 그림자, 산신의 사자

- 대본 요약: 그곳에는 판수가 몰래 넣어둔 마른 산나물 몇 줄기와 물 한 사발이 놓여 있었습니다. 노인은 연기처럼 서서히 어둠 속으로 스며들며 마지막 말을 남겼습니다. "지극한 정성이 하늘을 감동하게 하였으나, 그 대가는 가혹할 

- 프롬프트 요약: Tight two-shot at a famine-stricken Joseon village lane. an elderly father-in-law. Emotional intent is conveyed through gaze, posture, and p

- 판단 근거:

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 52 — 적합

- 챕터: 어둠 속의 그림자, 산신의 사자

- 대본 요약: 수련은 바들바들 떨리는 손으로 바닥의 물사발을 거머쥐었습니다. 시아버지가 제 피와 땀을 갈아 넣어 마련한 이 공간, 그리고 자신을 지켜주는 산신의 그림자. 그녀는 이것이 단순한 피신처가 아니라 판수가 목숨을 걸고 쌓

- 프롬프트 요약: Over-shoulder shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law kee

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 53 — 부분수정

- 챕터: 어둠 속의 그림자, 산신의 사자

- 대본 요약: 곡간 밖에서는 여전히 "아들아, 내 아들아!" 하고 외치는 판수의 가짜 광기가 처연하게 울려 퍼지고 있었습니다.

- 프롬프트 요약: Low-angle medium shot at a famine-stricken Joseon village lane. an elderly father-in-law. Emotional intent is conveyed through gaze, posture

- 판단 근거:

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 54 — 불일치

- 챕터: 굶주림이라는 첫 번째 시련

- 대본 요약: 마을의 식량은 이제 바닥을 넘어 먼지만이 가득했습니다. 산 사람의 눈은 퀭해지고, 서로를 바라보는 시선에는 굶주린 늑대의 살기가 서렸습니다. 관아에서 내려온 구휼미는 중간에서 증발한 듯 소식이 없고, 이장 최 씨는 

- 프롬프트 요약: Close-up at a Joseon county office courtyard. an elderly father-in-law and a corrupt village head. Rising anger is carried by sharp gaze, ti

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 55 — 불일치

- 챕터: 굶주림이라는 첫 번째 시련

- 대본 요약: "미친 노인네가 혼자 뭘 그리 처먹길래 아직도 숨이 붙어 있나 보자고! 분명 곡간에 쌀가마를 숨겨뒀을 게야!" 최 씨의 선동에 굶주린 마을 사람들이 판수의 마당으로 몰려들었습니다. 판수는 툇마루에 멍하니 앉아 침을 

- 프롬프트 요약: Tracking medium shot at a dim Joseon thatched-house interior. an elderly father-in-law and a corrupt village head. Emotional intent is conve

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 56 — 불일치

- 챕터: 굶주림이라는 첫 번째 시련

- 대본 요약: "헤헤, 아들이 밥을 달래네. 아들이 배가 고프대. 아무도 못 줘. 내 아들 밥이야." 판수는 품 안에서 무언가 눅눅한 덩어리를 꺼내 우물거렸습니다. 그것은 곡식이 아니라 산에서 캐온 칡뿌리와 진흙이 섞인 오물 같았

- 프롬프트 요약: High-angle wide shot at a famine-stricken Joseon village lane. an elderly father-in-law. Emotional intent is conveyed through gaze, posture,

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 57 — 불일치

- 챕터: 굶주림이라는 첫 번째 시련

- 대본 요약: 사람들은 역겨움에 고개를 돌렸습니다. 하지만 실상은 더 처참했습니다. 판수는 수련에게 줄 한 줌의 곡기를 마련하기 위해 자신의 끼니를 완전히 끊은 지 사흘째였습니다. 노인의 뱃가죽은 등뼈에 달라붙었고, 서 있을 기력

- 프롬프트 요약: Wide shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a rest

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 58 — 불일치

- 챕터: 굶주림이라는 첫 번째 시련

- 대본 요약: 그날 밤, 판수는 떨리는 손으로 곡간 벽의 작은 구멍을 통해 수련에게 무언가를 밀어 넣었습니다. 수련이 받아든 것은 온기가 느껴지는 작은 사발이었습니다. "아버님, 이건… 이건 무엇입니까? 비릿한 냄새가…." "묻지

- 프롬프트 요약: Medium shot at a dim Joseon thatched-house interior. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a res

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 59 — 불일치

- 챕터: 굶주림이라는 첫 번째 시련

- 대본 요약: 판수의 목소리는 끊어질 듯 가늘었습니다. 수련이 달빛 아래 사발을 비추자, 그 안에는 검붉은 피가 담겨 있었습니다. 판수가 자신의 손가락을 돌로 내리쳐 얻어낸 생혈(生血)이었습니다. 수련은 사발을 붙잡고 오열했습니다

- 프롬프트 요약: Tight two-shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law. Emotional intent is conveye

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 60 — 불일치

- 챕터: 굶주림이라는 첫 번째 시련

- 대본 요약: "어찌 이러십니까, 아버님! 제 목숨이 무엇이라고 이토록 모진 희생을 하신단 말입니까!" "울지 마라. 네 눈물이 내 피보다 더 아프구나." 판수는 벽 너머로 며느리의 울음소리를 들으며 차가운 흙바닥에 몸을 기댔습니

- 프롬프트 요약: Over-shoulder shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law kee

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 61 — 불일치

- 챕터: 굶주림이라는 첫 번째 시련

- 대본 요약: 굶주림은 창자를 끊어내는 고통이었으나, 곡간 안에서 들려오는 며느리의 숨소리는 판수를 버티게 하는 유일한 양식이었습니다. 수련은 시아버지의 피 묻은 사발을 가슴에 품고 다짐했습니다. 반드시 살아서, 이 은혜를 갚고야

- 프롬프트 요약: Low-angle medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law 

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 62 — 불일치

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: 마을에 감도는 공기는 이제 굶주림을 넘어 살기로 가득 찼습니다. 이장 최 씨는 판수가 곡간을 지키며 내뱉는 광언(狂言)이 더 이상 통하지 않음을 직감했습니다. 마을 사람들의 원성이 커지자, 그는 횃불을 든 장정들을 

- 프롬프트 요약: Close-up at a cold courtyard in front of a thatched house. an elderly father-in-law and a corrupt village head. Rising anger is carried by s

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 낮인데 대본상 야간 가능성이 높음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 63 — 불일치

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: "이보게들! 저 곡간 안에서 귀신 울음소리가 들린다는구먼. 저 요망한 기운 때문에 우리 마을에 비 한 방울 안 내리고 구휼미도 끊긴 것이야!" 최 씨의 선동에 눈이 뒤집힌 마을 사람들이 동조하기 시작했습니다. 최 씨

- 프롬프트 요약: Tracking medium shot at a famine-stricken Joseon village lane. a corrupt village head. Grief is readable in trembling posture, wet eyes, and

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 64 — 불일치

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: "저 곡간을 불태워 귀신을 쫓아내야 우리 마을이 산다! 판수 영감, 비키게! 아니면 자네도 저 안에서 아들 귀신이랑 같이 타 죽고 싶은가?" 판수는 눈을 부릅뜨고 곡간 문앞을 가로막았습니다. "안 된다! 이놈들아! 

- 프롬프트 요약: High-angle wide shot at a famine-stricken Joseon village lane. an elderly father-in-law. Urgent movement and pursuit shape the frame with di

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 65 — 불일치

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: 판수의 처절한 외침에도 최 씨는 아랑곳하지 않고 횃불을 곡간 처마 밑으로 가져다 댔습니다. '치직' 소리와 함께 마른 볏짚에 불꽃이 옮겨붙기 시작했습니다. 연기가 곡간 틈새로 스며들자, 판수의 가슴은 무너져 내렸습니

- 프롬프트 요약: Wide shot at a famine-stricken Joseon village lane. an elderly father-in-law and a corrupt village head. Flames and smoke shape the backgrou

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 낮인데 대본상 야간 가능성이 높음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 66 — 불일치

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: 수련이 그 안에 있었습니다. 이대로라면 며느리가 질식하거나 타 죽을 판이었습니다. "아이고, 내 아들아! 뜨겁지? 내가 꺼내주마! 내가 꺼내줄게!" 판수는 울부짖으며 오히려 불길 속으로 뛰어드는 시늉을 했습니다.

- 프롬프트 요약: Medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a re

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 67 — 불일치

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: 사람들은 비명을 지르며 물러났고, 그 혼란을 틈타 판수는 곡간 뒷벽의 비밀 통로로 기어 들어갔습니다. 연기가 자욱한 어둠 속에서 수련의 손을 낚아챈 판수의 눈빛이 번뜩였습니다. "수련아, 정신 차려라. 이제 더는 숨

- 프롬프트 요약: Tight two-shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 비밀 통로/토굴 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 68 — 불일치

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: 판수는 수련의 얼굴에 재를 묻히고 낡은 가마니를 씌웠습니다. 화마가 곡간을 집어삼키기 직전, 판수는 수련을 이끌고 뒷산으로 이어진 개구멍을 향했습니다. "이 화마를 틈타 마을을 빠져나가거라. 점복이가 산 너머 동막골

- 프롬프트 요약: Over-shoulder shot at a narrow winter mountain path near the village. an elderly father-in-law, a widowed daughter-in-law, and a nervous inf

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 69 — 불일치

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: 곡간이 무너져 내리는 굉음과 함께 판수는 수련을 밖으로 밀쳐냈습니다. 불길에 휩싸인 곡간을 뒤로하고, 판수는 다시 마을 사람들을 향해 달려 나갔습니다. "아들이 죽었다! 내 아들이 또 죽었어!" 그의 처절한 통곡 소

- 프롬프트 요약: Low-angle medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law. Flames and smoke sha

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 70 — 불일치

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: 더 뜨겁게 밤하늘을 수놓았습니다. §§CHAPTER|10|피보다 진한 연(緣)§§ 무너져 내리는 곡간의 서까래 사이로 매캐한 연기가 솟구칩니다.

- 프롬프트 요약: Close-up at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a restr

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 71 — 부분수정

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: 불길이 핥고 지나간 잿더미 근처, 판수는 넋이 나간 듯 주저앉아 타오르는 불꽃을 멍하니 바라보고 있었습니다. 마을 사람들은 귀신이 탔다며 침을 뱉고 흩어졌으나, 판수의 가슴은 갈기갈기 찢겨 나갔습니다. "아버님… 아

- 프롬프트 요약: Tracking medium shot at a famine-stricken Joseon village lane. an elderly father-in-law. Flames and smoke shape the background while figures

- 판단 근거:

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 72 — 적합

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: 그때였습니다. 뒷산 어귀 숲속에서 들려온 가냘픈 목소리. 판수는 황급히 고개를 돌렸습니다. 탈출한 줄 알았던 수련이 차마 발걸음이 떨어지지 않아 나무 뒤에 몸을 숨긴 채 울고 있었습니다.

- 프롬프트 요약: High-angle wide shot at a narrow winter mountain path near the village. an elderly father-in-law and a widowed daughter-in-law; the daughter

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 73 — 부분수정

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: 판수는 기어가는 몸짓으로 며느리에게 다가갔습니다. "왜 가지 않았느냐! 어서 산을 넘으라 하지 않았더냐!" 판수의 매서운 호통에 수련이 바닥에 넙죽 엎드렸습니다. 재투성이가 된 얼굴로 그녀가 판수의 소매를 붙잡았습니

- 프롬프트 요약: Wide shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law. Rising anger is carried by sharp

- 판단 근거:

  - 산길/숲 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 74 — 적합

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: "아버님을 이 사지에 두고 어찌 저만 살겠다고 가겠습니까. 차라리 저 불길 속에 저를 던지십시오. 남편도 잃고, 이제 시아버지마저 미치광이 취급을 받게 할 수는 없습니다." 판수는 잠시 멈칫하더니, 거친 손으로 수련

- 프롬프트 요약: Medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law. Flames and smoke shape the bac

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 75 — 적합

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: 아들을 잃고 난 후 처음으로 노부의 눈에서 뜨거운 눈물이 뚝뚝 떨어졌습니다. "수련아, 너는 내 며느리이기 전에 내 자식이다. 내 아들이 남기고 간 단 하나의 숨결이란 말이다. 네가 살아야 내 아들이 이 세상에 살다

- 프롬프트 요약: Tight two-shot at a famine-stricken Joseon village lane. a widowed daughter-in-law. Grief is readable in trembling posture, wet eyes, and re

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 76 — 부분수정

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: 곡간 벽을 사이에 두고 마음으로만 나누던 대화가 비로소 밖으로 터져 나왔습니다. 수련은 시아버지의 굽은 등 뒤로 비치는 불길 속에서, 돌아가신 남편의 인자한 미소를 본 듯했습니다. 경외심을 넘어선 천륜의 정이 두 사

- 프롬프트 요약: Over-shoulder shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law kee

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 77 — 적합

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: "가거라. 내 몸은 이미 늙고 병들어 저승 문턱에 닿아 있으나, 네 정조와 목숨만큼은 내 목숨을 다해서라도 지킬 것이다." 판수는 품 안에서 꼬깃꼬깃 접힌 종이 한 장을 꺼내 수련의 손에 쥐여주었습니다. 그것은 아들

- 프롬프트 요약: Low-angle medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law 

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 78 — 부분수정

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: "이것을 들고 살아남거라. 언젠가 이 서책이 너와 이 아비를 구할 날이 올 것이다." 판수는 수련을 어둠 속으로 거칠게 밀어냈습니다. 수련은 눈물을 닦으며 산등성이를 향해 달리기 시작했습니다. 판수는 멀어지는 며느리

- 프롬프트 요약: Close-up at a dim Joseon thatched-house interior. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a restra

- 판단 근거:

  - 산길/숲 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 79 — 적합

- 챕터: 첫 번째 반전 - 이장의 음모

- 대본 요약: "내 아들아! 불속에 내 아들이 있다!" 그의 비명은 밤하늘의 재가 되어 흩어졌습니다.

- 프롬프트 요약: Tracking medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law k

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 80 — 불일치

- 챕터: 관아의 포졸들이 들이닥치다

- 대본 요약: 불타버린 곡간의 매캐한 연기가 채 가시기도 전, 고치마을 어귀에 불길한 쇳소리가 울려 퍼집니다. 이장 최 씨의 고발을 받은 관아의 포졸들이 들이닥친 것입니다. 그들의 손에는 시퍼런 육방망이와 서슬 퍼런 포승줄이 들려

- 프롬프트 요약: High-angle wide shot at a Joseon county office courtyard. a corrupt village head and a stern constable. Flames and smoke shape the backgroun

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 81 — 불일치

- 챕터: 관아의 포졸들이 들이닥치다

- 대본 요약: "요사스러운 술법으로 민심을 어지럽히고, 죽은 자를 불러들여 곡간에 숨겼다는 자가 누구냐!" 포교의 서슬 퍼런 호령에 판수는 마당 한가운데 넋이 나간 듯 주저앉아 낄낄거리며 웃고 있었습니다. 최 씨는 기회를 놓치지 

- 프롬프트 요약: Wide shot at a Joseon county office courtyard. an elderly father-in-law, a corrupt village head, and a stern constable. Subtle emotional ten

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 82 — 불일치

- 챕터: 관아의 포졸들이 들이닥치다

- 대본 요약: "저 노인네입니다! 밤마다 곡간에서 귀신과 대화하며 마을의 운수를 막고, 이제는 곡간에 불까지 질러 증거를 없애려 했습니다!" 포졸들이 달려들어 판수의 멱살을 잡아 일으켰습니다. 노구의 몸이 허공에 붕 떴다 바닥으로

- 프롬프트 요약: Medium shot at a Joseon county office courtyard. an elderly father-in-law and a stern constable. A key evidence fragment is raised and inspe

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 83 — 불일치

- 챕터: 관아의 포졸들이 들이닥치다

- 대본 요약: "말해라! 곡간에 숨겼던 것이 무엇이냐! 네 며느리는 어디로 빼돌렸느냐!" 포교의 발길질이 판수의 옆구리를 강타했습니다. 판수는 고통에 몸을 비틀면서도 입가에 서린 기괴한 미소를 거두지 않았습니다. 그는 품 안에서 

- 프롬프트 요약: Tight two-shot at a Joseon county office courtyard. an elderly father-in-law, a widowed daughter-in-law, and a stern constable; the daughter

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 84 — 불일치

- 챕터: 관아의 포졸들이 들이닥치다

- 대본 요약: 그것은 불에 달궈져 뜨겁게 달아오른 곡간의 열쇠였습니다. "아들이… 아들이 여기 있다. 아무도 못 가져가…." 판수는 뜨거운 열쇠를 입안에 넣고 짓씹으며 으드득 소리를 냈습니다. 입술 사이로 검붉은 피가 배어 나왔으

- 프롬프트 요약: Over-shoulder shot at a famine-stricken Joseon village lane. an elderly father-in-law. Emotional intent is conveyed through gaze, posture, a

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 포교 등장 scene인데 관아 인물 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 85 — 불일치

- 챕터: 관아의 포졸들이 들이닥치다

- 대본 요약: 그 열쇠는 수련이 숨어 있는 비밀 통로로 이어지는 유일한 단서이자, 가문의 명예를 지키는 마지막 자물쇠였습니다. "이 독한 늙은이를 보게! 여봐라, 주리를 틀어서라도 입을 열게 하라!" 포졸들의 매질이 시작되었습니다

- 프롬프트 요약: Low-angle medium shot at a Joseon county office courtyard. an elderly father-in-law, a widowed daughter-in-law, and a stern constable; the d

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 비밀 통로/토굴 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 86 — 불일치

- 챕터: 관아의 포졸들이 들이닥치다

- 대본 요약: 몽둥이가 노인의 굽은 등을 때릴 때마다 마른 뼈 마디마디가 비명을 질렀으나, 판수는 신음 소리조차 내지 않았습니다. 그의 눈은 멀리 어두운 산등성이를 향해 있었습니다. '수련아… 돌아보지 마라.

- 프롬프트 요약: Close-up at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a restr

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 포교 등장 scene인데 관아 인물 정보가 프롬프트에 반영되지 않음

  - 산길/숲 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 87 — 불일치

- 챕터: 관아의 포졸들이 들이닥치다

- 대본 요약: 이 아비가 여기서 뼈가 가루가 되더라도, 너만은 저 산을 넘어야 한다.' 판수의 의식은 서서히 흐려져 갔습니다. 노쇠한 육신은 이미 한계에 다다랐으나, 입안의 뜨거운 열쇠만큼은 심장보다 더 뜨겁게 타오르고 있었습니다

- 프롬프트 요약: Tracking medium shot at a famine-stricken Joseon village lane. an elderly father-in-law. Flames and smoke shape the background while figures

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 포교 등장 scene인데 관아 인물 정보가 프롬프트에 반영되지 않음

  - 산길/숲 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 88 — 불일치

- 챕터: 관아의 포졸들이 들이닥치다

- 대본 요약: 최 씨는 판수의 강인함에 당황하며 침을 뱉었고, 마을 사람들은 차마 눈을 뜨지 못한 채 고개를 돌렸습니다.

- 프롬프트 요약: High-angle wide shot at a famine-stricken Joseon village lane. an elderly father-in-law and a corrupt village head. Emotional intent is conv

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 포교 등장 scene인데 관아 인물 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 89 — 불일치

- 챕터: 곡간 벽 뒤에 숨겨진 서책

- 대본 요약: 뒷산 어귀에 몸을 숨겼던 수련은 차마 발길을 떼지 못했습니다. 시아버지가 매질을 당하며 내지르는 둔탁한 소리가 산울림이 되어 가슴을 후벼팠기 때문입니다. 그녀는 판수가 마지막으로 쥐여준 낡은 보따리를 품에 꼭 안았습

- 프롬프트 요약: Wide shot at a narrow winter mountain path near the village. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law kee

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 90 — 불일치

- 챕터: 곡간 벽 뒤에 숨겨진 서책

- 대본 요약: "아버님을 이대로 죽게 둘 순 없어. 내 목숨을 버려서라도…." 수련은 보따리 안에서 아들의 유품이라던 낡은 서책을 꺼냈습니다. 그런데 달빛 아래 펼쳐진 서책의 내용은 단순한 문집이 아니었습니다. 그것은 죽은 남편이

- 프롬프트 요약: Medium shot at a Joseon county office courtyard. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a restrai

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 91 — 불일치

- 챕터: 곡간 벽 뒤에 숨겨진 서책

- 대본 요약: "이럴 수가… 이장 최 씨가 관아의 구휼미를 빼돌려 사사로이 팔아치운 기록이 아닌가!" 장부에는 날짜별로 빼돌린 쌀의 양과 그것을 사들인 상인들의 이름, 그리고 최 씨가 사또의 조카에게 바친 뇌물의 액수까지 낱낱이 

- 프롬프트 요약: Tight two-shot at a Joseon county office courtyard. a corrupt village head. A key evidence fragment is raised and inspected with focused urg

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 92 — 불일치

- 챕터: 곡간 벽 뒤에 숨겨진 서책

- 대본 요약: 수련의 손이 파르르 떨렸습니다. 그때, 장부의 낱장 사이에서 쥐가 갉아먹은 듯한 벽 틈새의 지도가 툭 떨어졌습니다. 그것은 불타버린 곡간 바닥, 판수가 수련을 숨겼던 그 토굴 너머에 또 다른 비밀함이 있음을 가리키고

- 프롬프트 요약: Over-shoulder shot at burned granary ruins with ash and broken beams. an elderly father-in-law and a widowed daughter-in-law; the daughter-i

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 비밀 통로/토굴 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 93 — 불일치

- 챕터: 곡간 벽 뒤에 숨겨진 서책

- 대본 요약: "아버님이 지키려 했던 것은 나뿐만이 아니었구나. 이 마을을 도탄에 빠뜨린 자들의 죄상을 지키고 계셨던 게야." 수련은 장부를 품속 깊이 밀어 넣었습니다. 이 서책은 이제 단순한 종이 뭉치가 아니었습니다. 판수의 굽

- 프롬프트 요약: Low-angle medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law 

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 94 — 불일치

- 챕터: 곡간 벽 뒤에 숨겨진 서책

- 대본 요약: 수련의 눈빛이 달라졌습니다. 슬픔에 젖어 흐릿하던 눈동자에는 서슬 퍼런 결기가 서렸습니다. 그녀는 산 아래, 횃불이 일렁이는 판수의 집 마당을 내려다보았습니다. 매질 소리가 멎고 정적이 찾아온 그곳으로, 수련은 다시

- 프롬프트 요약: Close-up at a dim Joseon thatched-house interior. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a restra

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 산길/숲 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 95 — 불일치

- 챕터: 곡간 벽 뒤에 숨겨진 서책

- 대본 요약: 도망치는 여인이 아니라, 진실을 거머쥔 가문의 주인으로서 말입니다.

- 프롬프트 요약: Tracking medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law k

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 96 — 불일치

- 챕터: 며느리의 각성

- 대본 요약: 어둠이 짙게 깔린 숲속, 수련은 품에 안은 서책의 무게가 천근만근처럼 느껴졌습니다. 시아버지가 매질을 당하면서도 왜 그토록 곡간 문을 부여잡고 광인 행세를 했는지, 왜 자신의 목숨보다 며느리의 안위를 우선했는지 비로

- 프롬프트 요약: High-angle wide shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law k

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 산길/숲 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 97 — 불일치

- 챕터: 며느리의 각성

- 대본 요약: "아버님은 나를 숨긴 것이 아니었다. 이 마을의 억울한 눈물을 닦아줄 진실을 지키고 계셨던 게야." 수련의 눈에서 흐르던 눈물이 멈췄습니다. 두려움에 떨며 시아버지의 등 뒤에 숨어 있던 유약한 여인의 모습은 온데간데

- 프롬프트 요약: Wide shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a rest

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 98 — 불일치

- 챕터: 며느리의 각성

- 대본 요약: 그녀는 서책을 비단 치마폭 안쪽에 단단히 묶었습니다. 몰락한 양반가의 여식으로 태어나 가난한 농부의 아내가 되었을 때도 잃지 않았던 기개가, 시아버지의 피 묻은 희생 앞에서 마침내 깨어난 것입니다. "나약하게 숨어 

- 프롬프트 요약: Medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a re

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 99 — 부분수정

- 챕터: 며느리의 각성

- 대본 요약: 수련은 산 아래를 내려다보았습니다. 판수의 집 마당에는 여전히 횃불이 넘실거리고, 최 씨의 가증스러운 고함이 산울림이 되어 들려왔습니다. 수련은 헝클어진 머리를 정갈하게 빗어 넘기고, 재투성이가 된 얼굴을 맑은 계곡

- 프롬프트 요약: Tight two-shot at a dim Joseon thatched-house interior. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head; the

- 판단 근거:

  - 산길/숲 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 100 — 불일치

- 챕터: 며느리의 각성

- 대본 요약: "이 서책이 빛을 발하는 순간, 아버님의 광기는 충절이 될 것이고 저들의 탐욕은 낱낱이 만천하에 드러날 것이다." 그녀는 이제 도망자가 아니었습니다. 가문을 살리고, 마을의 굶주림을 끝낼 강인한 여인으로 변모한 수련

- 프롬프트 요약: Over-shoulder shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law kee

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 산길/숲 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 101 — 불일치

- 챕터: 며느리의 각성

- 대본 요약: 한 걸음 한 걸음 내디딜 때마다, 그녀의 발걸음에는 시아버지를 구하고 진실을 밝히겠다는 서슬 퍼런 결의가 실렸습니다. 밤바람이 그녀의 치맛자락을 거칠게 흔들었으나, 수련의 눈빛은 북극성처럼 흔들림 없이 판수의 집을 

- 프롬프트 요약: Low-angle medium shot at a dim Joseon thatched-house interior. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law k

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 102 — 불일치

- 챕터: 며느리의 각성

- 대본 요약: §§CHAPTER|14|핵심 반전 - 죽은 아들의 귀환? §§ 판수의 마당에는 살벌한 정적이 감돌았습니다. 매질에 지친 판수는 피를 토하며 쓰러졌고, 이장 최 씨는 승리감에 도취하여 횃불을 높이 들었습니다.

- 프롬프트 요약: Close-up at a dim Joseon thatched-house interior. an elderly father-in-law and a corrupt village head. Emotional intent is conveyed through 

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 103 — 불일치

- 챕터: 며느리의 각성

- 대본 요약: "자, 이제 저 미친 늙은이의 곳간 바닥을 샅샅이 뒤져라! 귀신이건 곡식이건 숨어 있는 것을 다 끄집어내란 말이다!" 장정들이 달려들어 불에 타다 남은 곡간의 잔해를 거칠게 치웠습니다. 무거운 서까래가 들리고 바닥의

- 프롬프트 요약: Tracking medium shot at burned granary ruins with ash and broken beams. an elderly father-in-law. Emotional intent is conveyed through gaze,

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 104 — 적합

- 챕터: 며느리의 각성

- 대본 요약: 자욱한 먼지와 연기 사이로, 죽은 판수의 아들이 생전에 입었던 정갈한 관복 차림의 형체가 천천히 솟아올랐기 때문입니다. "어… 어버버! 귀, 귀신이다! 죽은 판수네 아들이 살아났다!" 사람들이 혼비백산하여 넘어지는 

- 프롬프트 요약: High-angle wide shot at a cold courtyard in front of a thatched house. an elderly father-in-law, a widowed daughter-in-law, and a corrupt vi

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 105 — 적합

- 챕터: 며느리의 각성

- 대본 요약: 달빛이 비친 그 얼굴은 죽은 아들이 아니었습니다. 남편의 관복을 입고, 머리를 정갈하게 빗어 넘긴 며느리 수련이었습니다. 그녀의 손에는 판수가 목숨 걸고 지켰던 낡은 서책이 들려 있었습니다. "이 마을에 귀신은 없다

- 프롬프트 요약: Wide shot at a famine-stricken Joseon village lane. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head; the dau

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 106 — 적합

- 챕터: 며느리의 각성

- 대본 요약: 수련의 목소리는 쩌렁쩌렁하게 마당을 울렸습니다. 당황한 최 씨가 삿대질하며 소리쳤습니다. "이, 이 요망한 것! 감히 죽은 남편의 옷을 입고 나와 사람들을 홀리려 드느냐! 당장 저년을 잡아라!" 수련은 피투성이가 되

- 프롬프트 요약: Medium shot at a cold courtyard in front of a thatched house. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village hea

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 107 — 부분수정

- 챕터: 며느리의 각성

- 대본 요약: "누가 누구를 잡는단 말이냐! 이 서책에는 네놈이 관아의 구휼미를 빼돌리고, 굶주린 백성들을 사지로 몰아넣은 죄상이 낱낱이 적혀 있다! 아버님께서 미친 척하며 이 곡간을 지키신 것은, 바로 이 증좌를 네놈들의 탐욕으

- 프롬프트 요약: Tight two-shot at a Joseon county office courtyard. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head; the dau

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 108 — 적합

- 챕터: 며느리의 각성

- 대본 요약: 판수가 왜 그토록 처절하게 광인 연기를 했는지, 왜 며느리를 숨겼는지에 대한 의문이 서서히 풀리기 시작했습니다. 수련의 형형한 눈빛은 이제 최 씨의 목을 겨누는 칼날처럼 서늘하게 빛나고 있었습니다.

- 프롬프트 요약: Over-shoulder shot at a dim Joseon thatched-house interior. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head;

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 109 — 불일치

- 챕터: 사지로 몰린 판수

- 대본 요약: "이, 이년이 무슨 헛소리를! 당장 그 가짜 종이 뭉치를 뺏어라!" 이장 최 씨의 얼굴이 흙빛으로 변했습니다. 자신의 치부가 담긴 서책이 수련의 손에 들려 있자, 그는 이성을 잃고 날뛰기 시작했습니다. 하지만 수련의

- 프롬프트 요약: Low-angle medium shot at a Joseon county office courtyard. an elderly father-in-law, a widowed daughter-in-law, a corrupt village head, and 

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 110 — 부분수정

- 챕터: 사지로 몰린 판수

- 대본 요약: "가까이 오지 마라! 한 걸음이라도 움직이면 이 미친 노인네의 목줄기를 따버리겠다!" 날카로운 칼날이 판수의 주름진 목덜미를 파고들었습니다. 가느다란 핏줄기가 노인의 하얀 수염을 적셨습니다. 수련은 숨이 멎는 듯한 

- 프롬프트 요약: Close-up at a dim Joseon thatched-house interior. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head; the daugh

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 111 — 부분수정

- 챕터: 사지로 몰린 판수

- 대본 요약: 판수는 고통 속에서도 흐릿한 눈을 떠 수련을 바라보았습니다. 그의 입술은 피범벅이 된 채로 무언가 간절히 속삭이고 있었습니다. '…보지 마라. 멈추지 마라.'

- 프롬프트 요약: Tracking medium shot at a dim Joseon thatched-house interior. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village hea

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 112 — 적합

- 챕터: 사지로 몰린 판수

- 대본 요약: 판수는 최 씨의 칼날을 두려워하기보다, 며느리가 자신 때문에 진실을 포기할까 봐 더 두려워하고 있었습니다. 최 씨는 광기 어린 눈으로 수련을 노려보며 윽박질렀습니다. "그 서책을 당장 이 횃불 속에 던져라! 그렇지 

- 프롬프트 요약: High-angle wide shot at a dim Joseon thatched-house interior. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village hea

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 113 — 부분수정

- 챕터: 사지로 몰린 판수

- 대본 요약: 마당을 가득 메운 마을 사람들은 숨을 죽였습니다. 판수가 흘리는 피가 차가운 마당 흙바닥으로 스며들었고, 수련의 손에 든 서책은 분노로 인해 파르르 떨리고 있었습니다. 모든 것을 잃을 위기 속에서 수련은 선택해야 했

- 프롬프트 요약: Wide shot at a cold courtyard in front of a thatched house. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head;

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 114 — 적합

- 챕터: 사지로 몰린 판수

- 대본 요약: 시아버지의 목숨인가, 아니면 마을 전체를 구할 진실인가. "아버님… 아버님…!" 수련의 절규가 밤공기를 찢었습니다. 최 씨는 비릿한 미소를 지으며 칼에 힘을 주었고, 판수는 마지막 기력을 다해 최 씨의 팔을 움켜쥐었

- 프롬프트 요약: Medium shot at a famine-stricken Joseon village lane. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head; the d

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 115 — 부분수정

- 챕터: 사지로 몰린 판수

- 대본 요약: 노구의 마지막 저항은 처절했으나, 이미 사지로 몰린 노인의 생명줄은 위태롭게 흔들리고 있었습니다.

- 프롬프트 요약: Tight two-shot at a dim Joseon thatched-house interior. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head; the

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 116 — 부분수정

- 챕터: 수련의 최후 통첩

- 대본 요약: 최 씨의 서슬 퍼런 칼날이 판수의 목줄기를 겨누자, 수련의 눈동자에 맺혔던 눈물이 분노의 불꽃으로 타올랐습니다. 그녀는 뒷걸음질 치는 대신, 관복 소매를 펄럭이며 최 씨를 향해 당당히 한 걸음을 내디뗐습니다. "쏘아

- 프롬프트 요약: Over-shoulder shot at a dim Joseon thatched-house interior. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head;

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 117 — 불일치

- 챕터: 수련의 최후 통첩

- 대본 요약: 수련은 서책을 높이 들어 올린 채, 마을 사람들을 향해 고개를 돌렸습니다. 그녀의 목소리는 굶주림에 지친 백성들의 가슴을 찌르는 비수가 되었습니다. "보시오, 고치마을 사람들이여! 경신년 오월 초사흘, 구휼미 서른 

- 프롬프트 요약: Low-angle medium shot at a Joseon county office courtyard. a widowed daughter-in-law, a corrupt village head, and an elderly father-in-law; 

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 118 — 불일치

- 챕터: 수련의 최후 통첩

- 대본 요약: 수련이 낭독하는 장부의 내용은 구체적이고도 참혹했습니다. 굶어 죽은 아이들의 이름과 최 씨가 쌀을 빼돌린 날짜가 하나하나 불려 나오자, 웅성거리던 마을 사람들의 눈빛이 돌변했습니다. "이, 이년이… 닥치지 못할까!"

- 프롬프트 요약: Close-up at a dim Joseon thatched-house interior. a widowed daughter-in-law, a corrupt village head, and an elderly father-in-law; the daugh

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 119 — 적합

- 챕터: 수련의 최후 통첩

- 대본 요약: 수련은 멈추지 않고 최 씨의 눈을 똑바로 응시하며 마지막 승부수를 던졌습니다. "아버님을 놓아주어라! 지금 당장 이 서책을 든 내 수하가 관아를 향해 달리고 있다! 네놈이 아버님의 털끝 하나라도 건드린다면, 네 삼족

- 프롬프트 요약: Tracking medium shot at a Joseon county office courtyard. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head; t

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 120 — 불일치

- 챕터: 수련의 최후 통첩

- 대본 요약: 수련의 서슬 퍼런 기개에 최 씨는 압도되었습니다. 장부를 든 그녀의 손은 떨림이 없었고, 그 위엄은 마치 죽은 아들이 돌아와 호령하는 듯했습니다. 마을 사람들은 이제 최 씨를 향해 하나둘씩 몽둥이를 고쳐 쥐기 시작했

- 프롬프트 요약: High-angle wide shot at a famine-stricken Joseon village lane. a widowed daughter-in-law, a corrupt village head, and an elderly father-in-l

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 121 — 불일치

- 챕터: 수련의 최후 통첩

- 대본 요약: 시아버지를 인질로 잡은 최 씨의 비겁함과 만천하에 드러난 그의 악행이, 굶주린 백성들의 마지막 인내심을 끊어버린 순간이었습니다.

- 프롬프트 요약: Wide shot at a famine-stricken Joseon village lane. an elderly father-in-law and a corrupt village head. Emotional intent is conveyed throug

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 122 — 불일치

- 챕터: 절정 - 불타는 곡간 앞의 대결

- 대본 요약: "네, 네놈들이 감히 누구에게 매를 드느냐! 내가 이 마을의 법이다!" 최 씨가 악에 받쳐 소리를 질렀으나, 이미 굶주림보다 더 깊은 분노가 마을 사람들의 눈을 덮었습니다. 수련이 낭독한 장부의 한 구절 한 구절은 

- 프롬프트 요약: Medium shot at a famine-stricken Joseon village lane. a widowed daughter-in-law and a corrupt village head. A key evidence fragment is raise

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 123 — 불일치

- 챕터: 절정 - 불타는 곡간 앞의 대결

- 대본 요약: "우리 애가 굶어 죽어갈 때, 네놈 곳간에는 쌀이 썩어 나갔단 말이냐!" 마을 장정 하나가 쇠스랑을 치켜들며 달려들자, 최 씨의 수하들이 앞을 가로막았습니다. 타다 남은 곡간의 불씨가 다시금 밤바람에 살아나며 마당은

- 프롬프트 요약: Tight two-shot at a cold courtyard in front of a thatched house. a corrupt village head. Emotional intent is conveyed through gaze, posture,

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 124 — 불일치

- 챕터: 절정 - 불타는 곡간 앞의 대결

- 대본 요약: 몽둥이가 부딪히는 소리와 비명이 뒤섞이고, 최 씨는 인질로 잡은 판수를 방패 삼아 뒤로 물러나려 했습니다. "가까이 오지 마! 오면 정말 이 늙은이를 죽이겠다!" 그때였습니다. 피투성이가 되어 의식을 잃은 줄 알았던

- 프롬프트 요약: Over-shoulder shot at a famine-stricken Joseon village lane. an elderly father-in-law and a corrupt village head. Emotional intent is convey

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 125 — 적합

- 챕터: 절정 - 불타는 곡간 앞의 대결

- 대본 요약: "으아악!" 최 씨가 비명을 지르며 중심을 잃고 비틀거린 찰나, 마을 사람들이 파도처럼 몰려와 최 씨를 덮쳤습니다. 수련은 주저 없이 불길을 뚫고 달려가 판수를 품에 안았습니다. "아버님! 정신 차리십시오! 아버님!

- 프롬프트 요약: Low-angle medium shot at a famine-stricken Joseon village lane. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village h

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 126 — 부분수정

- 챕터: 절정 - 불타는 곡간 앞의 대결

- 대본 요약: 판수는 흐릿한 시야 속에서 남편의 관복을 입은 수련을 보았습니다. 노인은 며느리의 얼굴에 묻은 재를 닦아내려 떨리는 손을 뻗었습니다. "살았구나… 내 자식이 살았어…." 마당 한편에서는 최 씨와 그의 수하들이 분노한

- 프롬프트 요약: Close-up at a dim Joseon thatched-house interior. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head; the daugh

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 127 — 불일치

- 챕터: 절정 - 불타는 곡간 앞의 대결

- 대본 요약: 불타는 곡간의 잔해 위로 튀어 오르는 불꽃은 마치 고치마을의 억눌린 한이 터져 나오는 듯했습니다. 판수의 희생과 수련의 기개가 일구어낸 이 처절한 난투극 속에서, 수백 년을 이어온 산골 마을의 거짓된 평화가 무너져 

- 프롬프트 요약: Tracking medium shot at burned granary ruins with ash and broken beams. an elderly father-in-law and a widowed daughter-in-law; the daughter

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 128 — 부분수정

- 챕터: 드러난 추악한 진실

- 대본 요약: 아수라장이 된 마당 한복판, 마을 장정들에게 제압당한 최 씨가 흙바닥에 짓눌려 비명을 질렀습니다. 수련은 판수를 부축해 일으키며, 품 안에서 장부의 마지막 장을 찢어 최 씨의 면전에 내던졌습니다. "네놈의 정체가 고

- 프롬프트 요약: High-angle wide shot at a cold courtyard in front of a thatched house. an elderly father-in-law, a widowed daughter-in-law, and a corrupt vi

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 129 — 불일치

- 챕터: 드러난 추악한 진실

- 대본 요약: 최 씨의 눈동자가 경악으로 뒤물들었습니다. 수련의 목소리는 칼날처럼 서늘하게 마당을 갈랐습니다. "본명은 최달석. 이십 년 전 영남 일대를 피로 물들였던 도적 떼 '흑운당'의 부두목이 아니더냐! 신분을 세탁하고 이 

- 프롬프트 요약: Wide shot at a cold courtyard in front of a thatched house. a widowed daughter-in-law and a corrupt village head. Blade threat is visible wi

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 130 — 불일치

- 챕터: 드러난 추악한 진실

- 대본 요약: 마을 사람들이 술렁였습니다. 단순한 탐관오리인 줄 알았던 이장의 정체가 흉악한 도적이었다는 사실에 분노는 공포를 넘어 경멸로 변했습니다. 판수가 왜 그토록 목숨을 걸고 곡간을 지켰는지, 이제 모든 의문이 풀렸습니다.

- 프롬프트 요약: Medium shot at a Joseon county office courtyard. an elderly father-in-law and a corrupt village head. A key evidence fragment is raised and 

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 131 — 불일치

- 챕터: 드러난 추악한 진실

- 대본 요약: "아버님은… 아드님이 남긴 이 진실을 지키기 위해 미치광이 행세를 하신 게야. 이 장부가 세상에 나오면 네놈이 우리 가문을 가만두지 않을 것을 아셨기에, 스스로를 가두고 며느리인 나마저 숨기며 때를 기다리신 것이란 

- 프롬프트 요약: Tight two-shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 132 — 부분수정

- 챕터: 드러난 추악한 진실

- 대본 요약: 판수를 미친 노인이라 손가락질하고, 그가 곡간에 귀신을 들였다며 침을 뱉었던 자신들의 어리석음이 비수가 되어 가슴을 찔렀습니다. 최 씨는 이제 변명조차 하지 못한 채 사시나무 떨듯 떨었습니다. 판수는 며느리의 부축을

- 프롬프트 요약: Over-shoulder shot at a famine-stricken Joseon village lane. an elderly father-in-law, a widowed daughter-in-law, and a corrupt village head

- 판단 근거:

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 133 — 불일치

- 챕터: 드러난 추악한 진실

- 대본 요약: 노인의 입가에는 피가 흐르고 있었으나, 그 눈빛만은 이십 년 전 아들을 잃었을 때보다 더 형형하게 빛나고 있었습니다. "아들아… 이제야 네 숙제를 다 끝냈구나. 내 며느리가… 내 자식이 해냈어." 판수의 마른 손이 

- 프롬프트 요약: Low-angle medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law 

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 134 — 불일치

- 챕터: 드러난 추악한 진실

- 대본 요약: 잿더미가 된 곡간 뒤로 새벽안개가 밀려오고, 추악한 진실이 밝혀진 마당에는 서늘한 정의의 기운이 감돌기 시작했습니다.

- 프롬프트 요약: Close-up at a cold courtyard in front of a thatched house. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps

- 판단 근거:

  - 장면 등장인물 3명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 화염/소실 연출이 대본 근거보다 과함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 135 — 불일치

- 챕터: 갈등 해소와 보상

- 대본 요약: 동틀 녘의 서늘한 공기를 가르고 관아의 관찰사가 직접 거느린 수십 명의 군관들이 고치마을 마당을 메웠습니다. 수련이 미리 점복이를 통해 관아에 연줄을 대어 놓았던 덕분입니다. 포박된 이장 최 씨와 그 수하들은 변명 

- 프롬프트 요약: Tracking medium shot at a Joseon county office courtyard. a widowed daughter-in-law, a corrupt village head, and a nervous informant. Restra

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 136 — 불일치

- 챕터: 갈등 해소와 보상

- 대본 요약: "이 장부에 적힌 죄상이 사실이라면, 네놈은 목숨이 열 개라도 모자랄 것이다!" 관찰사의 호령 아래, 최 씨가 숨겨두었던 비밀 창고의 문이 부서졌습니다. 그 안에는 마을 사람들이 굶어 죽어갈 때 빼돌린 구휼미 가마니

- 프롬프트 요약: High-angle wide shot at a famine-stricken Joseon village lane. a corrupt village head. A key evidence fragment is raised and inspected with 

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 137 — 불일치

- 챕터: 갈등 해소와 보상

- 대본 요약: 쌀가마가 마당으로 쏟아지자 사람들은 통곡하며 바닥을 쳤습니다. "이 쌀이 우리 애 입으로 들어갔어야 했는데…!" 관찰사는 판수의 앞에 다가와 허리를 숙였습니다. "노인장의 충절과 인내, 그리고 이 부인의 용기가 아니

- 프롬프트 요약: Wide shot at a Joseon county office courtyard. an elderly father-in-law. Grief is readable in trembling posture, wet eyes, and restrained mo

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 138 — 불일치

- 챕터: 갈등 해소와 보상

- 대본 요약: 며칠 후, 관아에서는 수련에게 '열녀문'을 하사하겠다는 소식을 전해왔습니다. 흉흉한 세상에 보기 드문 효심과 정절을 지켰다는 이유였습니다. 하지만 수련은 정중히 거절하며 관찰사 앞에 엎드렸습니다. "소부는 가문의 명

- 프롬프트 요약: Medium shot at a Joseon county office courtyard. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a restrai

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 139 — 불일치

- 챕터: 갈등 해소와 보상

- 대본 요약: 수련의 청에 관찰사는 감복하여 고개를 끄덕였습니다. 판수는 비로소 깨끗한 의복을 입고 툇마루에 앉아 며느리가 올리는 따뜻한 쌀밥을 마주했습니다. 노인의 패인 주름 사이로 흐르던 고통의 흔적은 온데간데없고, 그저 자식

- 프롬프트 요약: Tight two-shot at a dim Joseon thatched-house interior. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a 

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 140 — 불일치

- 챕터: 갈등 해소와 보상

- 대본 요약: 고치마을의 긴 겨울은 그렇게 끝나가고 있었습니다. 곡간을 채운 것은 쌀만이 아니었습니다. 서로를 의심하고 미워했던 마음 대신, 판수와 수련이 보여준 지독한 희생에 대한 경외심이 마을 사람들의 가슴속에 새로운 씨앗으로

- 프롬프트 요약: Over-shoulder shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law kee

- 판단 근거:

  - 장면 등장인물 4명 대비 프롬프트 인물 수가 적음

  - 최 씨 존재 scene인데 악역/이장 정보가 프롬프트에 반영되지 않음

  - 곡간/곳간 문맥인데 프롬프트 장소 반영이 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 141 — 부분수정

- 챕터: 고치마을의 매화

- 대본 요약: 시베리아의 칼바람이 잦아들고, 고치마을의 꽁꽁 얼어붙었던 계곡물이 졸졸 소리를 내며 흐르기 시작했습니다. 판수의 집 마당, 불타버린 곡간이 있던 자리에는 마을 사람들이 힘을 모아 새로 지어 올린 작고 정갈한 곳간이 

- 프롬프트 요약: Low-angle medium shot at burned granary ruins with ash and broken beams. an elderly father-in-law. Flames and smoke shape the background whi

- 판단 근거:

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 142 — 부분수정

- 챕터: 고치마을의 매화

- 대본 요약: "아버님, 올해는 매화가 유난히 일찍 꽃망울을 터뜨렸습니다." 수련이 툇마루에 앉아 햇볕을 쬐는 판수의 무릎에 두툼한 겉옷을 덮어주며 말합니다. 판수는 이제 지팡이 없이도 마당을 거닐 만큼 기력을 회복했습니다. 그의

- 프롬프트 요약: Close-up at a dim Joseon thatched-house interior. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a restra

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 143 — 적합

- 챕터: 고치마을의 매화

- 대본 요약: "허허, 그러게나 말이다. 작년 그 모진 서리를 견뎌내더니, 기어이 향기를 내뿜는구나." 판수의 시선이 머문 곳에는 연분홍빛 매화가 수줍게 고개를 내밀고 있었습니다. 그것은 마치 굶주림과 핍박 속에서도 절개를 지켜낸

- 프롬프트 요약: Tracking medium shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law k

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 144 — 적합

- 챕터: 고치마을의 매화

- 대본 요약: 마을 아이들은 이제 판수를 '미친 노인'이라 부르며 도망치지 않습니다. 대신 수련의 방 앞에 옹기종기 모여 앉아, 그녀가 가르쳐주는 천자문 읽는 소리를 낭랑하게 울려 퍼뜨립니다. "진정한 효와 의는 남에게 보이기 위

- 프롬프트 요약: High-angle wide shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law k

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 145 — 부분수정

- 챕터: 고치마을의 매화

- 대본 요약: 수련이 아이들에게 전하는 목소리에는 시아버지로부터 배운 삶의 도리가 담겨 있었습니다. 마을 사람들은 이제 판수의 집 앞을 지날 때면 경건하게 발걸음을 멈추고 고개를 숙입니다. 그들이 본 것은 한 미치광이 노인의 기행

- 프롬프트 요약: Wide shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a rest

- 판단 근거:

  - 프롬프트가 야간 고정인데 대본상 야간 근거가 약함

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 146 — 부분수정

- 챕터: 고치마을의 매화

- 대본 요약: 봄바람이 불어와 매화 꽃잎 하나가 판수의 손등 위에 살포시 내려앉습니다. 노인은 그 꽃잎을 조심스레 쥐며 먼 산을 바라봅니다. 아마도 하늘에 있는 아들에게 '이제야 네 아내를 온전히 지켜냈노라'고 전하고 있는지도 모

- 프롬프트 요약: Medium shot at a famine-stricken Joseon village lane. an elderly father-in-law. Emotional intent is conveyed through gaze, posture, and purp

- 판단 근거:

  - 수련 존재 scene인데 수련 역할이 프롬프트에 반영되지 않음

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


## Scene 147 — 적합

- 챕터: 고치마을의 매화

- 대본 요약: 고치마을의 매화 향기는 담장을 넘어 온 마을로 퍼져 나갔습니다. 흉년의 상처는 아물어가고, 판수와 수련이 심은 희망의 싹은 새로운 계절을 맞아 더욱 단단하게 뿌리를 내리고 있었습니다.

- 프롬프트 요약: Tight two-shot at a famine-stricken Joseon village lane. an elderly father-in-law and a widowed daughter-in-law; the daughter-in-law keeps a

- 판단 근거:

  - 프롬프트가 장면 고유정보보다 범용 템플릿 의존


---

# Codex 전달용 최종 작업지시서

이 문서는 단순 검수 메모가 아니라, **scene 이미지 프롬프트를 실제로 수정하기 위한 작업 명세서**다. Codex는 아래 지시를 우선순위대로 적용해야 한다.

## 1. 작업 목표

목표는 `project.json`의 `scenes[].llm_clip_prompt`를 수정하여 다음 두 조건을 동시에 만족시키는 것이다.

1. 각 scene 프롬프트가 **대본 흐름과 장면 문맥에 맞게** 구체화될 것
2. 사용자가 요청한 **지브리 스타일 이미지 방향**이 충돌 없이 일관되게 반영될 것

수정 대상은 기본적으로 `llm_clip_prompt` 및 필요시 해당 scene의 `image.prompt_original`, `image.prompt_used` 재생성 로직에 연결되는 프롬프트 문자열이다.

## 2. 절대 규칙

### 2-1. 대본 우선 원칙
- scene 프롬프트는 반드시 해당 scene의 `text`, `sentences`, `characters`, `places`, `chapter_title`를 기준으로 작성한다.
- 범용 템플릿 문구보다 **현재 scene 고유 정보**를 우선한다.
- 이전/이후 scene 분위기를 참고할 수는 있지만, 현재 scene에 없는 사건을 추가하지 않는다.

### 2-2. 야간 자동 주입 금지
- 대본에 밤, 심야, 달빛, 횃불, 어둠, 야음, 한밤중 등의 근거가 없으면 `night`, `moonlit`, `dark night`, `at night`, `torch-lit night` 같은 표현을 넣지 않는다.
- 시간대가 불명확하면 기본값은 **낮 또는 흐린 낮**이다.
- 계절/정황상 서늘하고 음산한 분위기가 필요해도, 야간으로 단정하지 말고 `cold winter daylight`, `overcast daylight`, `pale morning light` 같은 식으로 처리한다.

### 2-3. 장소 정확도 우선
- `places`에 연결된 장소 메타를 보고 scene 배경을 결정한다.
- 아래 규칙을 강제 적용한다.
  - `place_001` = 고치마을 들판 / 마을 어귀 / 마른 논바닥 계열
  - `place_002` = 판수의 초가집 내부 / 툇마루 / 집 안
  - `place_003` = 판수 집 마당 / 대문 / 앞마당
  - `place_004` = 관아 앞마당
  - `place_005` = 불탄 곡간 / 곡간 폐허 / 재와 그을음 / 무너진 들보
  - `place_006` = 뒷산 숲길 / 겨울 산길 / 안개 낀 산등성이
  - `place_007` = 토굴 비밀 통로 / 좁은 흙벽 통로 / 숨겨진 석문
  - `place_008` = 계곡 은신처 / 바위 / 물안개 / 외딴 은신처
- `village field and alley` 같은 범용 표현은 `place_001` 계열일 때만 제한적으로 사용한다.
- `place_005`, `place_006`, `place_007`, `place_008` scene에서는 장소가 프롬프트 본문에 명시적으로 드러나야 한다.

### 2-4. 등장인물 정확도 우선
- `characters`와 `character_instances`를 보고 scene 핵심 인물을 명시한다.
- `hungry villagers`, `people`, `villagers` 같은 뭉뚱그린 표현은 실제로 군중 scene일 때만 사용한다.
- 주요 캐릭터는 아래 명칭과 속성으로 반영한다.
  - `char_001` 판수 = elderly stubborn farmer, gaunt elderly man, father-in-law
  - `char_002` 수련 = young widowed daughter-in-law, determined young woman
  - `char_003` 최 씨 = greedy village head Choi, suspicious middle-aged man
  - `char_004` 점복이 = nervous fortuneteller, thin middle-aged villager
  - `char_005` 포교 = intimidating constable, government enforcer
- 수련/최 씨/포교가 있는 scene에서 generic villager 표현만 남겨두지 않는다.
- 후반부 `관복_위장` variant가 적용된 수련 scene은 **변장 상태**가 드러나야 한다.

### 2-5. 화풍 단일화 규칙
- 최종 목표 화풍은 **Ghibli-inspired hand-drawn 2D animation**이다.
- `Korean manhwa/webtoon look`, `k_webtoon`, `webtoon look` 같은 표현은 scene 프롬프트 본문에서 제거한다.
- 다만 조선 시대 한국적 인상, 한국인 얼굴 비율, 조선 복식 연속성은 유지한다.
- 즉, **화풍은 지브리풍**, **인물/복식/배경 고증 방향은 조선 시대 한국풍**으로 유지한다.

### 2-6. 금지 사항
- 대본에 없는 감정 과장, 액션, 전투, 추격을 임의로 추가하지 않는다.
- 동일한 템플릿 문장을 모든 scene에 반복 삽입하지 않는다.
- 아래 표현은 필요할 때만 제한적으로 사용하고, 기계적으로 반복하지 않는다.
  - `Clear facial expression, focused gaze, and active body gesture`
  - `no text or speech bubbles`
  - `Outdoor village courtyard at night with clear environment depth`
  - `famine-stricken Joseon village field and alley`
- scene와 맞지 않는 `courtyard`, `alley`, `night`를 자동으로 붙이지 않는다.

## 3. 수정 우선순위

다음 구간을 우선 수정한다.

### 최우선
- Scene 1~6
  - 초반 배경 정립 구간
  - 서리, 흉년, 마른 논바닥, 죽은 느티나무, 적막한 마을이 핵심
  - 군중 과다/야간 고정 제거 필요

- Scene 14~22
  - 초가집과 인물 관계 구간
  - 판수, 수련, 최 씨, 점복이의 관계와 공간감이 더 분명해야 함

- Scene 54~61
  - 관아 및 시련 구간
  - 관아/행정 압박/긴장 구조가 명확해야 함

- Scene 80~88
  - 포교 난입/관아 압박 구간
  - 포교의 위압성과 공권력의 침입이 살아야 함

- Scene 102~134
  - 수련의 위장, 대결, 진실 폭로, 후반 반전 구간
  - `관복_위장`과 후반 갈등 축을 분명히 반영해야 함

### 차우선
- Scene 7~13
- Scene 23~53
- Scene 62~79
- Scene 89~101
- Scene 135~147

## 4. scene 작성 규칙

각 scene 프롬프트는 아래 항목을 가능하면 모두 포함하되, 장면에 맞게 자연스럽게 작성한다.

1. 샷 타입
   - wide shot / medium shot / close-up / over-shoulder / tracking shot 등

2. 정확한 장소
   - 예: burned granary ruins, thatched-house porch, hidden earthen tunnel, mountain forest path

3. 핵심 인물
   - 누가 주도 인물인지 명시

4. 핵심 행동 또는 상황
   - 예: 판수가 마른 논을 내려친다, 수련이 시아버지를 부축한다, 포교가 들이닥친다, 최 씨가 압박한다

5. 감정 톤
   - grief, suspicion, exhaustion, dread, resolve, confrontation, quiet recovery 등

6. 시간/빛
   - 대본 근거가 있을 때만 night/moonlit/torch-lit 사용
   - 아니면 daylight / cold daylight / dim interior / overcast daylight 등으로 처리

7. 화풍
   - `Ghibli-inspired hand-drawn animation`, `painterly background`, `soft but expressive character acting` 등으로 일관화

8. 공통 제약
   - no visible text, no speech bubbles
   - Joseon-era wardrobe continuity
   - Korean/East-Asian facial proportions

## 5. 출력 형식

Codex는 결과를 아래 방식으로 정리한다.

### 5-1. 수정 파일
- 실제 `project.json` 안의 해당 scene `llm_clip_prompt`를 직접 수정한다.

### 5-2. 변경 보고서
별도 markdown 파일 하나를 만들어 아래 형식으로 기록한다.

```md
## Scene 001
- old_prompt: ...
- issue_tags: [night_mismatch, generic_background, style_conflict]
- new_prompt: ...
- rationale: 대본상 초겨울 서리와 마른 논바닥이 핵심이므로 군중/야간 중심 템플릿 제거
```

## 6. 스타일 충돌 해결 규칙

현재 프로젝트는 `style_profile: k_webtoon`이지만, 사용자 요구는 지브리 스타일이다. 따라서 scene 프롬프트에서는 아래 기준을 따른다.

- 남길 것
  - hand-drawn
  - Ghibli-inspired
  - painterly background
  - expressive but natural character acting
  - warm/cool cinematic color harmony

- 제거할 것
  - Korean manhwa/webtoon look
  - stylized 2D Korean webtoon look
  - webtoon 기반이라는 직접 문구

- 유지할 것
  - Joseon-era Korean setting
  - Korean facial proportions
  - Joseon wardrobe continuity

## 7. 후반부 특수 규칙

- Scene 102~108
  - 수련의 변장 단서가 보여야 한다.
  - 단순 평복 여성으로 남기지 않는다.

- Scene 109~121
  - 판수, 수련, 최 씨 간 대립 구도가 더 선명해야 한다.
  - generic crowd scene로 흐리지 않는다.

- Scene 122~134
  - 절정/대결/진실 폭로에 맞게 장면 긴장도를 올리되, 대본에 없는 과도한 액션은 넣지 않는다.

- Scene 141~147
  - 후반 회복 국면이다.
  - 더 이상 흉년 초반의 극단적 절망 템플릿을 반복하지 않는다.
  - 매화, 봄빛, 회복, 존중, 교육, 희망의 정서가 살아야 한다.

## 8. 최종 품질 체크리스트

각 scene 수정 후 아래를 확인한다.

- 이 프롬프트만 봐도 scene 장소가 맞는가?
- 등장인물이 맞는가?
- 대본의 핵심 행동/감정이 들어갔는가?
- 대본에 없는 night/moonlit가 들어가 있지 않은가?
- generic villager 템플릿으로 뭉개지지 않았는가?
- 지브리풍과 웹툰풍이 충돌하지 않는가?
- 앞뒤 scene와 비교해도 중복 템플릿이 과하지 않은가?

## 9. Codex에 대한 직접 지시

Codex는 이 문서를 참고자료가 아니라 **실행 명세서**로 취급한다.  
가능하면 한 번에 전체 scene를 수정하되, 어렵다면 우선순위 구간부터 정확하게 고친다.  
모호할 때는 범용 문구를 반복하지 말고, scene의 `text`, `characters`, `places`를 다시 읽고 구체화한다.
