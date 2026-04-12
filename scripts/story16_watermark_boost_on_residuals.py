#!/usr/bin/env python3
from __future__ import annotations

import argparse, json
from pathlib import Path
import cv2
import numpy as np


def residual_score(img: np.ndarray, cx: int, cy: int) -> float:
    h,w=img.shape[:2]
    rr=max(10,int(min(h,w)*0.018))
    x0=max(0,cx-rr);x1=min(w,cx+rr+1);y0=max(0,cy-rr);y1=min(h,cy+rr+1)
    roi=img[y0:y1,x0:x1]
    hsv=cv2.cvtColor(roi,cv2.COLOR_BGR2HSV)
    gray=cv2.cvtColor(roi,cv2.COLOR_BGR2GRAY).astype(np.float32)
    hp=np.clip(gray-cv2.GaussianBlur(gray,(0,0),1.8),0,None)
    return float(((hsv[:,:,2]>150)&(hsv[:,:,1]<95)&(hp>5)).mean())


def build_mask(h:int,w:int,cx:int,cy:int,s:int)->np.ndarray:
    m=np.zeros((h,w),np.uint8)
    pts=np.array([[cx,cy-s],[cx+s,cy],[cx,cy+s],[cx-s,cy]],np.int32)
    cv2.fillConvexPoly(m,pts,255)
    cv2.ellipse(m,(cx,cy),(int(s*2.1),max(1,int(s*0.65))),0,0,360,255,-1)
    cv2.ellipse(m,(cx,cy),(max(1,int(s*0.65)),int(s*2.1)),0,0,360,255,-1)
    m=cv2.GaussianBlur(m,(0,0),1.0)
    _,m=cv2.threshold(m,38,255,cv2.THRESH_BINARY)
    return m


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',default='work/story16/clips_manual_clicked')
    ap.add_argument('--coords',default='work/story16/out/watermark_compare/manual_coords_clicked.json')
    ap.add_argument('--output',default='work/story16/clips_manual_clicked_boost')
    ap.add_argument('--debug-dir',default='work/story16/out/watermark_compare/boost_debug')
    ap.add_argument('--threshold',type=float,default=0.12)
    args=ap.parse_args()

    in_dir=Path(args.input); out_dir=Path(args.output); dbg=Path(args.debug_dir)
    out_dir.mkdir(parents=True,exist_ok=True); dbg.mkdir(parents=True,exist_ok=True)
    coords={r['file']:r for r in json.loads(Path(args.coords).read_text())}

    boosted=0; done=0
    for p in sorted(in_dir.glob('*.png')):
        img=cv2.imread(str(p));
        if img is None: continue
        h,w=img.shape[:2]
        row=coords.get(p.name)
        if not row:
            cv2.imwrite(str(out_dir/p.name),img); done+=1; continue
        cx,cy=int(row['cx']),int(row['cy'])
        s0=residual_score(img,cx,cy)
        out=img.copy(); mask=np.zeros((h,w),np.uint8)
        if s0>=args.threshold:
            base=max(9,int(min(h,w)*0.017))
            if s0>=0.22:
                mult=1.30
            elif s0>=0.16:
                mult=1.18
            else:
                mult=1.08
            s=max(10,int(base*mult))
            mask=build_mask(h,w,cx,cy,s)
            out=cv2.inpaint(out,mask,3.2,cv2.INPAINT_TELEA)
            out=cv2.inpaint(out,mask,2.2,cv2.INPAINT_TELEA)
            boosted+=1
        cv2.imwrite(str(out_dir/p.name),out)

        x0,y0=int(w*0.84),int(h*0.80)
        co=img[y0:h,x0:w]; cm=cv2.cvtColor(mask[y0:h,x0:w],cv2.COLOR_GRAY2BGR); cn=out[y0:h,x0:w]
        up=lambda a: cv2.resize(a,(a.shape[1]*2,a.shape[0]*2),interpolation=cv2.INTER_NEAREST)
        tile=np.hstack([up(co),up(cm),up(cn)])
        cv2.putText(tile,f"{p.name} s0={s0:.3f} boosted={s0>=args.threshold}",(8,22),cv2.FONT_HERSHEY_SIMPLEX,0.56,(255,255,255),2,cv2.LINE_AA)
        cv2.imwrite(str(dbg/p.name),tile)
        done+=1

    print(f'done: {done}, boosted: {boosted}')
    print(f'out: {out_dir}')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
