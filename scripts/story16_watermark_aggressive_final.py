#!/usr/bin/env python3
from __future__ import annotations

import argparse, json
from pathlib import Path
import cv2
import numpy as np


def build_aggressive_mask(h:int,w:int,cx:int,cy:int)->np.ndarray:
    m=np.zeros((h,w),np.uint8)
    s=max(11,int(min(h,w)*0.022))
    pts=np.array([[cx,cy-s],[cx+s,cy],[cx,cy+s],[cx-s,cy]],np.int32)
    cv2.fillConvexPoly(m,pts,255)
    cv2.ellipse(m,(cx,cy),(int(s*2.35),max(1,int(s*0.72))),0,0,360,255,-1)
    cv2.ellipse(m,(cx,cy),(max(1,int(s*0.72)),int(s*2.35)),0,0,360,255,-1)
    # glow ring
    cv2.circle(m,(cx,cy),int(s*1.35),255,-1)
    m=cv2.GaussianBlur(m,(0,0),1.25)
    _,m=cv2.threshold(m,28,255,cv2.THRESH_BINARY)
    return m


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',default='work/story16/clips_manual_clicked_boost')
    ap.add_argument('--coords',default='work/story16/out/watermark_compare/manual_coords_clicked.json')
    ap.add_argument('--output',default='work/story16/clips_manual_final')
    ap.add_argument('--debug-dir',default='work/story16/out/watermark_compare/final_aggressive_debug')
    args=ap.parse_args()

    in_dir=Path(args.input); out_dir=Path(args.output); dbg=Path(args.debug_dir)
    out_dir.mkdir(parents=True,exist_ok=True); dbg.mkdir(parents=True,exist_ok=True)
    coords={r['file']:r for r in json.loads(Path(args.coords).read_text())}

    done=0
    for p in sorted(in_dir.glob('*.png')):
        img=cv2.imread(str(p))
        if img is None: continue
        h,w=img.shape[:2]
        r=coords.get(p.name)
        if not r:
            cv2.imwrite(str(out_dir/p.name),img); done+=1; continue
        cx,cy=int(r['cx']),int(r['cy'])
        mask=build_aggressive_mask(h,w,cx,cy)
        out=cv2.inpaint(img,mask,3.6,cv2.INPAINT_TELEA)
        out=cv2.inpaint(out,mask,2.6,cv2.INPAINT_TELEA)
        cv2.imwrite(str(out_dir/p.name),out)

        x0,y0=int(w*0.84),int(h*0.80)
        co=img[y0:h,x0:w]; cm=cv2.cvtColor(mask[y0:h,x0:w],cv2.COLOR_GRAY2BGR); cn=out[y0:h,x0:w]
        up=lambda a: cv2.resize(a,(a.shape[1]*2,a.shape[0]*2),interpolation=cv2.INTER_NEAREST)
        tile=np.hstack([up(co),up(cm),up(cn)])
        cv2.putText(tile,f'{p.name} c=({cx},{cy})',(8,22),cv2.FONT_HERSHEY_SIMPLEX,0.56,(255,255,255),2,cv2.LINE_AA)
        cv2.imwrite(str(dbg/p.name),tile)
        done+=1

    print('done',done)
    print('out',out_dir)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
