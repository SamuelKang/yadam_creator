#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import cv2, numpy as np

WORST = {
    '051.png','056.png','036.png','033.png','141.png','024.png','020.png','162.png','071.png','069.png',
    '075.png','073.png','079.png','072.png','074.png','011.png','034.png','037.png','176.png','178.png'
}


def score(img,cx,cy):
    h,w=img.shape[:2]; rr=max(10,int(min(h,w)*0.018))
    x0=max(0,cx-rr);x1=min(w,cx+rr+1);y0=max(0,cy-rr);y1=min(h,cy+rr+1)
    roi=img[y0:y1,x0:x1]
    hsv=cv2.cvtColor(roi,cv2.COLOR_BGR2HSV)
    g=cv2.cvtColor(roi,cv2.COLOR_BGR2GRAY).astype(np.float32)
    hp=np.clip(g-cv2.GaussianBlur(g,(0,0),1.8),0,None)
    return float(((hsv[:,:,2]>150)&(hsv[:,:,1]<95)&(hp>5)).mean())


def local_center(img,cx,cy):
    h,w=img.shape[:2]
    rr=max(14,int(min(h,w)*0.03))
    x0=max(0,cx-rr);x1=min(w,cx+rr+1);y0=max(0,cy-rr);y1=min(h,cy+rr+1)
    roi=img[y0:y1,x0:x1]
    hsv=cv2.cvtColor(roi,cv2.COLOR_BGR2HSV)
    g=cv2.cvtColor(roi,cv2.COLOR_BGR2GRAY).astype(np.float32)
    hp=np.clip(g-cv2.GaussianBlur(g,(0,0),2.0),0,None)
    m=((hsv[:,:,2]>145)&(hsv[:,:,1]<110)&(hp>4)).astype(np.uint8)
    ys,xs=np.where(m>0)
    if len(xs)==0:
        return cx,cy
    return int(x0+xs.mean()), int(y0+ys.mean())


def mask(h,w,cx,cy,s):
    m=np.zeros((h,w),np.uint8)
    pts=np.array([[cx,cy-s],[cx+s,cy],[cx,cy+s],[cx-s,cy]],np.int32)
    cv2.fillConvexPoly(m,pts,255)
    cv2.ellipse(m,(cx,cy),(int(s*2.4),max(1,int(s*0.75))),0,0,360,255,-1)
    cv2.ellipse(m,(cx,cy),(max(1,int(s*0.75)),int(s*2.4)),0,0,360,255,-1)
    cv2.circle(m,(cx,cy),int(s*1.5),255,-1)
    m=cv2.GaussianBlur(m,(0,0),1.25)
    _,m=cv2.threshold(m,24,255,cv2.THRESH_BINARY)
    return m

coords={r['file']:r for r in json.loads(Path('work/story16/out/watermark_compare/manual_coords_clicked.json').read_text())}
in_dir=Path('work/story16/clips_manual_final')
out_dir=Path('work/story16/clips_manual_final2'); out_dir.mkdir(parents=True,exist_ok=True)
dbg=Path('work/story16/out/watermark_compare/final2_targeted_debug'); dbg.mkdir(parents=True,exist_ok=True)

for p in sorted(in_dir.glob('*.png')):
    img=cv2.imread(str(p)); h,w=img.shape[:2]
    out=img.copy()
    r=coords.get(p.name)
    if r and p.name in WORST:
        cx,cy=int(r['cx']),int(r['cy'])
        cx2,cy2=local_center(img,cx,cy)
        s=max(12,int(min(h,w)*0.024))
        m=np.bitwise_or(mask(h,w,cx,cy,s),mask(h,w,cx2,cy2,max(10,int(s*0.9))))
        out=cv2.inpaint(out,m,3.8,cv2.INPAINT_TELEA)
        out=cv2.inpaint(out,m,2.8,cv2.INPAINT_TELEA)
    cv2.imwrite(str(out_dir/p.name),out)

    if r and p.name in WORST:
        cx,cy=int(r['cx']),int(r['cy'])
        s0=score(img,cx,cy); s1=score(out,cx,cy)
        x0,y0=int(w*0.84),int(h*0.80)
        co=img[y0:h,x0:w]; cn=out[y0:h,x0:w]
        up=lambda a: cv2.resize(a,(a.shape[1]*2,a.shape[0]*2),interpolation=cv2.INTER_NEAREST)
        tile=np.hstack([up(co),up(cn)])
        cv2.putText(tile,f'{p.name} {s0:.3f}->{s1:.3f}',(8,22),cv2.FONT_HERSHEY_SIMPLEX,0.58,(255,255,255),2,cv2.LINE_AA)
        cv2.imwrite(str(dbg/p.name),tile)

print('done')
