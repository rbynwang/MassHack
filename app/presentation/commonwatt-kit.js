/* =====================================================================
   MassWatt 3D kit
   Reusable white-clay architecture, energy-flow lines and lighting for
   MassWatt visuals (story scenes, system diagrams, stills, GLB export).

   Classic script: defines window.CommonwattKit(THREE, X). The page imports
   three.js and passes the addons it needs in X:
     mergeGeometries, RoomEnvironment, EffectComposer, RenderPass, GTAOPass,
     OutputPass, Line2, LineMaterial, LineGeometry, GLTFExporter

   Units are meters. World axes: +x east, +y up, +z south (toward the street).
   Every building has a local frame with the same axes, origin at the center
   of its footprint on the ground, front facade facing +z.
   ===================================================================== */
(function(){
'use strict';

window.CommonwattKit = function(THREE, X){

/* options: foliage off gives the clean white-model look (no trees or shrubs) */
const OPT = { foliage: false, people: false };
const DEG = Math.PI/180;
const V3 = (x,y,z) => new THREE.Vector3(x,y,z);
const lerp = (a,b,t) => a+(b-a)*t;
function rng(seed){ let s = (seed*2654435761)>>>0 || 1; return () => { s ^= s<<13; s>>>=0; s ^= s>>>17; s ^= s<<5; s>>>=0; return s/4294967296; }; }

/* ---------- palette ---------- */
const PAL = { solar:'#36c56c', battery:'#f2a63a', grid:'#2fb5ae', strain:'#e9533f', signal:'#6268f2', wire:'#8d939a' };

/* ---------- textures ---------- */
function canvasTex(w, h, draw){
  const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t;
}
const pvTex = canvasTex(128, 224, (g, w, h) => {
  g.fillStyle = '#c8cdd2'; g.fillRect(0,0,w,h);
  g.fillStyle = '#121826'; g.fillRect(4,4,w-8,h-8);
  const cols = 6, rows = 10, cw = (w-12)/cols, ch = (h-12)/rows;
  for(let i=0;i<cols;i++) for(let j=0;j<rows;j++){
    const x = 6+i*cw, y = 6+j*ch, gr = g.createLinearGradient(x,y,x+cw,y+ch);
    gr.addColorStop(0,'#2a3550'); gr.addColorStop(1,'#182033');
    g.fillStyle = gr; g.fillRect(x+0.6,y+0.6,cw-1.2,ch-1.2);
  }
  g.strokeStyle = 'rgba(190,200,220,.18)'; g.lineWidth = 1;
  for(let i=1;i<3;i++){ const x = 6+i*(w-12)/3; g.beginPath(); g.moveTo(x,6); g.lineTo(x,h-6); g.stroke(); }
});
const radialTex = canvasTex(128, 128, (g, w, h) => {
  const gr = g.createRadialGradient(w/2,h/2,0,w/2,h/2,w/2);
  gr.addColorStop(0,'rgba(255,255,255,1)'); gr.addColorStop(0.45,'rgba(255,255,255,.45)'); gr.addColorStop(1,'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0,0,w,h);
});

/* ---------- materials ---------- */
function std(color, rough, metal, extra){ return new THREE.MeshStandardMaterial(Object.assign({ color, roughness: rough ?? 0.9, metalness: metal ?? 0 }, extra || {})); }
const MAT = {
  clay:     std('#f3f2ee', .88),
  clay2:    std('#e7e6e1', .9),
  clay3:    std('#d6d5cf', .9),
  trim:     std('#fbfbf9', .8),
  brick:    std('#e9e1d6', .93),
  shingle:  std('#4a4e55', .9),
  roof:     std('#3f4349', .85),
  concrete: std('#e3e3df', .96),
  wood:     std('#c29b74', .7),
  wood2:    std('#8d6b4b', .72),
  floor:    std('#cbb497', .8),
  fabric:   std('#d8d2c6', .95),
  accent:   std('#7f9384', .9),
  awning:   std('#6f8c79', .9),
  book1:    std('#c6b49b', .9), book2: std('#a4b0b3', .9), book3: std('#d9cfbf', .9), book4: std('#b89a86', .9),
  people:   std('#dad8d1', .8),
  metal:    std('#cdd1d5', .5, .35),
  metalDark:std('#6f757c', .55, .4),
  grille:   std('#363a40', .7, .3),
  dark:     std('#2a2e33', .6),
  white:    std('#fdfdfb', .32),
  carpaint: std('#8c949e', .34, .3),
  carglass: std('#2a3038', .08, .25),
  tail:     std('#a3302a', .5, 0, { emissive:'#c0392b', emissiveIntensity:.35 }),
  pv:       std('#ffffff', .32, .25, { map: pvTex }),
  glass:    new THREE.MeshPhysicalMaterial({ color:'#a7bac4', roughness:.05, metalness:0, transparent:true, opacity:.24, envMapIntensity:1.1, depthWrite:false }),
  room:     std('#8a7e70', .9, 0, { emissive:'#ffc77a', emissiveIntensity:0 }),
  roomDim:  std('#6f6a64', .9, 0, { emissive:'#ffc77a', emissiveIntensity:0 }),
  lamp:     std('#fff6e4', .5, 0, { emissive:'#ffd497', emissiveIntensity:0 }),
  led:      new THREE.MeshBasicMaterial({ color: PAL.solar }),
  trunk:    std('#bdb6a8', .9),
  ground:   std('#dadbda', 1),
  asphalt:  std('#d2d3d2', .97),
  sidewalk: std('#e6e6e5', .95),
  paint:    std('#fbfbf9', .8),
  grass:    std('#d8dbcf', 1),
  water:    std('#cfd8da', .2, .1),
  ctx:      std('#efefec', .95),
  ctxRoof:  std('#e3e3e0', .95),
  ctxWin:   std('#c9cccd', .6, 0, { emissive:'#ffc77a', emissiveIntensity:0 }),
  ctxWin2:  std('#d3d5d5', .6, 0, { emissive:'#ffc77a', emissiveIntensity:0 })
};
const NOCAST = new Set(['glass','led','room','roomDim','floor','paint','grass','asphalt','sidewalk','ground']);
const leafMat = new THREE.MeshStandardMaterial({ color:'#ffffff', roughness:.95, flatShading:true });
/* foliage tones, dark to light */
const LEAF = {
  tree:  ['#959b66','#a3a870','#b2b47b','#c1c087','#cdca93','#d9d6a2'],
  hedge: ['#8e9a76','#9ca784','#abb493','#bac2a3']
};

/* ---------- geometry builder: accumulates parts, merges per material ---------- */
const UNIT_BOX = new THREE.BoxGeometry(1,1,1);
const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _e = new THREE.Euler(), _s = new THREE.Vector3(), _p = new THREE.Vector3(), _up = new THREE.Vector3(0,1,0);
function clean(g){ g = g.index ? g.toNonIndexed() : g.clone(); for(const k of Object.keys(g.attributes)) if(k!=='position' && k!=='normal' && k!=='uv') g.deleteAttribute(k); return g; }

class Builder {
  constructor(seed){ this.parts = new Map(); this.leaves = []; this.r = rng(seed || 7); }
  addM(mat, geo, m){ const g = clean(geo); g.applyMatrix4(m); let a = this.parts.get(mat); if(!a) this.parts.set(mat, a = []); a.push(g); return this; }
  add(mat, geo, x, y, z, rx, ry, rz, sx, sy, sz){
    _e.set(rx||0, ry||0, rz||0, 'YXZ'); _q.setFromEuler(_e); _p.set(x||0, y||0, z||0); _s.set(sx??1, sy??1, sz??1);
    return this.addM(mat, geo, _m.compose(_p, _q, _s));
  }
  /* center x/z, bottom y0 */
  box(mat, cx, y0, cz, w, h, d, ry, rx, rz){ return this.add(mat, UNIT_BOX, cx, y0+h/2, cz, rx, ry, rz, w, h, d); }
  /* fully centered */
  boxC(mat, cx, cy, cz, w, h, d, rx, ry, rz){ return this.add(mat, UNIT_BOX, cx, cy, cz, rx, ry, rz, w, h, d); }
  cyl(mat, cx, y0, cz, r, h, seg, rTop){ return this.add(mat, new THREE.CylinderGeometry(rTop ?? r, r, h, seg || 16), cx, y0+h/2, cz); }
  /* disk/cylinder whose axis points along x (axis='x') or z (axis='z') */
  disk(mat, axis, cx, cy, cz, r, t, seg){ const g = new THREE.CylinderGeometry(r, r, t, seg || 24); return axis==='x' ? this.add(mat, g, cx, cy, cz, 0, 0, Math.PI/2) : this.add(mat, g, cx, cy, cz, Math.PI/2, 0, 0); }
  sphere(mat, x, y, z, r, ws, hs){ return this.add(mat, new THREE.SphereGeometry(r, ws || 14, hs || 10), x, y, z); }
  /* a strut between two points */
  seg(mat, a, b, t){
    const d = _p.set(b[0]-a[0], b[1]-a[1], b[2]-a[2]); const len = d.length(); if(len < 1e-4) return this;
    _q.setFromUnitVectors(_up, d.clone().normalize()); _s.set(t, len, t);
    _m.compose(V3((a[0]+b[0])/2, (a[1]+b[1])/2, (a[2]+b[2])/2), _q, _s);
    return this.addM(mat, UNIT_BOX, _m);
  }
  leaf(x, y, z, r, tone, pal){ const p = LEAF[pal || 'tree']; this.leaves.push({ x, y, z, r, c: p[Math.floor(tone*p.length) % p.length] }); return this; }
  shrub(x, y0, z, r, n){
    if(!OPT.foliage) return this;
    const R = this.r; n = n || Math.round(6 + r*8);
    n = n*3;
    for(let i=0;i<n;i++){ const a = R()*Math.PI*2, d = R()*r*0.85, yy = R(); this.leaf(x+Math.cos(a)*d, y0+r*0.3+yy*r*0.75, z+Math.sin(a)*d, r*(0.2+R()*0.18), Math.min(0.999, yy*0.7+R()*0.3), 'hedge'); }
    return this;
  }
  tree(x, z, s, seed, y0){
    if(!OPT.foliage) return this;
    const R = rng(seed || 3); s = s || 1; y0 = y0 || 0;
    const h = 4.3*s;
    this.cyl('trunk', x, y0, z, 0.17*s, h, 9, 0.11*s);
    const nb = 5;
    for(let i=0;i<nb;i++){
      const a = i/nb*Math.PI*2 + R()*0.9, tilt = 0.5 + R()*0.45, len = (2.0 + R()*1.4)*s;
      const dx = Math.sin(a)*Math.sin(tilt), dy = Math.cos(tilt), dz = Math.cos(a)*Math.sin(tilt);
      const bx = x, by = y0 + h*(0.62 + R()*0.25), bz = z;
      this.seg('trunk', [bx, by, bz], [bx+dx*len, by+dy*len, bz+dz*len], 0.13*s);
    }
    const cy = y0 + h + 1.5*s, nc = 6 + Math.floor(R()*3);
    const cl = [[0, cy+0.7*s, 0, 1.9*s]];
    for(let i=0;i<nc;i++){ const a = R()*Math.PI*2, d = (1.0+R()*0.9)*s; cl.push([Math.cos(a)*d, cy - 0.4*s + R()*1.7*s, Math.sin(a)*d, (1.15+R()*0.6)*s]); }
    for(const [cx, ccy, cz, rc] of cl){
      const n = Math.round(rc*rc*26);
      for(let i=0;i<n;i++){
        let u = R()*2-1, v = R()*2-1, w = R()*2-1; const L = Math.hypot(u, v, w) || 1; const k = (0.72 + R()*0.3)/L;
        const py = ccy + v*k*rc*0.85, lt = Math.min(0.999, Math.max(0, (py - (cy - 2.2*s))/(4.6*s)*0.75 + R()*0.3));
        this.leaf(x+cx+u*k*rc, py, z+cz+w*k*rc, (0.2+R()*0.17)*s, lt);
      }
    }
    return this;
  }
  build(name){
    const grp = new THREE.Group(); grp.name = name || '';
    for(const [key, list] of this.parts){
      const merged = X.mergeGeometries(list, false);
      if(!merged){ console.warn('commonwatt-kit: could not merge', key); continue; }
      const mesh = new THREE.Mesh(merged, MAT[key]); mesh.name = (name || '') + ':' + key;
      mesh.castShadow = !NOCAST.has(key); mesh.receiveShadow = key !== 'glass' && key !== 'led';
      if(key === 'glass' || key === 'led') mesh.userData.noAO = true;
      grp.add(mesh);
    }
    return grp;
  }
}

/* ---------- facade helpers ---------- */
/* F = {axis:'z'|'x', at, sign}: a wall plane. u runs along the wall (x for 'z' walls, z for 'x' walls). */
const FACE = (axis, at, sign) => ({ axis, at, sign: sign || 1 });
function fbox(bb, F, mat, u, v0, w, du, dv, dw){
  if(F.axis === 'z') bb.box(mat, u, v0, F.at + F.sign*w, du, dv, dw);
  else bb.box(mat, F.at + F.sign*w, v0, u, dw, dv, du);
}
function win(bb, F, u0, u1, v0, v1, o){
  o = o || {};
  const cu = (u0+u1)/2, du = u1-u0, dv = v1-v0, t = o.frame ?? 0.09, fm = o.frameMat || 'trim';
  if(o.room !== false) fbox(bb, F, (o.lit ?? bb.r()) < 0.72 ? 'room' : 'roomDim', cu, v0, 0.015, du, dv, 0.03);
  fbox(bb, F, 'glass', cu, v0, 0.06, du, dv, 0.02);
  fbox(bb, F, fm, cu, v1, 0.07, du+2*t, t, 0.14);
  fbox(bb, F, fm, cu, v0-t, 0.07, du+2*t, t, 0.14);
  fbox(bb, F, fm, u0-t/2, v0, 0.07, t, dv, 0.14);
  fbox(bb, F, fm, u1+t/2, v0, 0.07, t, dv, 0.14);
  for(let i=1;i<=(o.mull||0);i++) fbox(bb, F, fm, u0+du*i/((o.mull||0)+1), v0, 0.08, 0.05, dv, 0.1);
  if(o.transom) fbox(bb, F, fm, cu, v0+dv*o.transom, 0.08, du, 0.05, 0.1);
  if(o.sill !== false) fbox(bb, F, fm, cu, v0-t-0.07, 0.12, du+2*t+0.18, 0.07, 0.26);
  if(o.lintel) fbox(bb, F, o.lintel, cu, v1+t, 0.1, du+2*t+0.3, 0.22, 0.2);
}

/* ---------- people and furniture (local coords, rotated by ry about y) ---------- */
function R(bb, x, y0, z, ry){
  ry = ry || 0; const c = Math.cos(ry), s = Math.sin(ry);
  const P = (dx, dz) => [x + dx*c + dz*s, z - dx*s + dz*c];
  const api = {
    box(mat, dx, dy, dz, w, h, d, rx){ const p = P(dx, dz); bb.box(mat, p[0], y0+dy, p[1], w, h, d, ry, rx); return api; },
    cyl(mat, dx, dy, dz, r, h, seg, rt){ const p = P(dx, dz); bb.cyl(mat, p[0], y0+dy, p[1], r, h, seg, rt); return api; },
    sph(mat, dx, dy, dz, r){ const p = P(dx, dz); bb.sphere(mat, p[0], y0+dy, p[1], r); return api; },
    geo(mat, geo, dx, dy, dz, rx, rz){ const p = P(dx, dz); bb.add(mat, geo, p[0], y0+dy, p[1], rx, ry, rz); return api; }
  };
  return api;
}
const G_HEAD = new THREE.SphereGeometry(0.11, 14, 10), G_TORSO = new THREE.CapsuleGeometry(0.155, 0.42, 4, 10);
const G_LEG = new THREE.CapsuleGeometry(0.068, 0.62, 3, 8), G_SHIN = new THREE.CapsuleGeometry(0.062, 0.36, 3, 8), G_ARM = new THREE.CapsuleGeometry(0.05, 0.5, 3, 8);
function figure(bb, x, y0, z, ry, pose){
  if(!OPT.people) return;
  const r = R(bb, x, y0, z, ry);
  if(pose === 'sit'){
    r.geo('people', G_TORSO, 0, 0.98, -0.06).geo('people', G_HEAD, 0, 1.46, -0.04);
    r.geo('people', G_LEG, -0.1, 0.52, 0.2, Math.PI/2).geo('people', G_LEG, 0.1, 0.52, 0.2, Math.PI/2);
    r.geo('people', G_SHIN, -0.1, 0.25, 0.52).geo('people', G_SHIN, 0.1, 0.25, 0.52);
    r.geo('people', G_ARM, -0.22, 0.98, 0.08, 0.5).geo('people', G_ARM, 0.22, 0.98, 0.08, 0.5);
  } else {
    const sw = pose === 'walk' ? 0.34 : 0.03;
    r.geo('people', G_LEG, -0.1, 0.45, 0, sw).geo('people', G_LEG, 0.1, 0.45, 0, -sw);
    r.geo('people', G_TORSO, 0, 1.13, 0).geo('people', G_HEAD, 0, 1.63, 0);
    r.geo('people', G_ARM, -0.24, 1.1, 0, -sw*0.8).geo('people', G_ARM, 0.24, 1.1, 0, sw*0.8);
  }
}
function sofa(bb, x, y0, z, ry, w){
  w = w || 2.4;
  R(bb, x, y0, z, ry).box('dark', 0, 0, 0, w-0.1, 0.1, 0.84).box('fabric', 0, 0.1, 0.05, w-0.3, 0.34, 0.8)
    .box('fabric', 0, 0.1, -0.36, w, 0.78, 0.2).box('fabric', -w/2+0.11, 0.1, 0.02, 0.22, 0.6, 0.9).box('fabric', w/2-0.11, 0.1, 0.02, 0.22, 0.6, 0.9)
    .box('accent', -w/4, 0.44, -0.18, 0.5, 0.36, 0.12, -0.25).box('accent', w/4, 0.44, -0.18, 0.5, 0.36, 0.12, -0.25);
}
function table(bb, x, y0, z, ry, w, d, h, mat){
  w = w || 1.6; d = d || 0.8; h = h || 0.74;
  const r = R(bb, x, y0, z, ry); r.box(mat || 'wood', 0, h-0.05, 0, w, 0.05, d);
  [[-1,-1],[1,-1],[-1,1],[1,1]].forEach(([a,b]) => r.box('metalDark', a*(w/2-0.07), 0, b*(d/2-0.07), 0.045, h-0.05, 0.045));
}
function roundTable(bb, x, y0, z, rad){ rad = rad || 0.38; bb.cyl('wood', x, y0+0.71, z, rad, 0.04, 24); bb.cyl('metalDark', x, y0, z, 0.03, 0.71, 8); bb.cyl('metalDark', x, y0, z, 0.24, 0.025, 16); }
function chair(bb, x, y0, z, ry, mat){
  const r = R(bb, x, y0, z, ry); mat = mat || 'wood';
  r.box(mat, 0, 0.43, 0, 0.44, 0.05, 0.44).box(mat, 0, 0.48, -0.2, 0.44, 0.42, 0.04);
  [[-1,-1],[1,-1],[-1,1],[1,1]].forEach(([a,b]) => r.box('metalDark', a*0.19, 0, b*0.19, 0.03, 0.43, 0.03));
}
function potPlant(bb, x, y0, z, s){ s = s || 1; bb.cyl('clay2', x, y0, z, 0.2*s, 0.42*s, 14, 0.25*s); bb.shrub(x, y0+0.3*s, z, 0.5*s, 7); }
function bookshelf(bb, x, y0, z, ry, w, h, levels){
  const r = R(bb, x, y0, z, ry); levels = levels || 4; w = w || 3; h = h || 2.1;
  r.box('wood', 0, 0, 0, w, 0.06, 0.42).box('wood', -w/2+0.03, 0, 0, 0.05, h, 0.42).box('wood', w/2-0.03, 0, 0, 0.05, h, 0.42).box('wood', 0, h-0.05, 0, w, 0.05, 0.42);
  const mats = ['book1','book2','book3','book4'];
  for(let l=0;l<levels;l++){
    const y = 0.08 + l*(h-0.15)/levels;
    r.box('wood', 0, y-0.02, 0, w-0.1, 0.03, 0.4);
    let u = -w/2+0.1;
    while(u < w/2-0.25){ const bw = 0.25 + bb.r()*0.5, bh = (h/levels)*(0.55+bb.r()*0.25); r.box(mats[Math.floor(bb.r()*4)], u+bw/2, y+0.01, 0.02, bw-0.02, bh, 0.3); u += bw; }
  }
}
function pvPanel(bb, cx, cy, cz, w, d, tilt, rz){ bb.boxC('pv', cx, cy, cz, w, 0.045, d, tilt || 0, 0, rz || 0); }
function pvArray(bb, x0, z0, y, cols, rows, pw, pd, gx, gz, tilt){
  for(let r=0;r<rows;r++) for(let c=0;c<cols;c++){
    const cx = x0 + c*(pw+gx) + pw/2, cz = z0 + r*(pd+gz) + pd/2, lift = Math.sin(tilt)*pd/2;
    pvPanel(bb, cx, y+0.35+lift, cz, pw, pd, tilt);
    bb.box('metal', cx-pw/2+0.12, y, cz-pd/2+0.15, 0.05, 0.35+lift*2, 0.05).box('metal', cx+pw/2-0.12, y, cz-pd/2+0.15, 0.05, 0.35+lift*2, 0.05);
    bb.box('metal', cx-pw/2+0.12, y, cz+pd/2-0.15, 0.05, 0.3, 0.05).box('metal', cx+pw/2-0.12, y, cz+pd/2-0.15, 0.05, 0.3, 0.05);
  }
}
function heatPump(bb, x, y0, z, faceX){
  bb.box('concrete', x, y0, z, faceX ? 0.9 : 1.4, 0.1, faceX ? 1.4 : 0.9);
  if(faceX){ bb.box('metal', x, y0+0.1, z, 0.48, 0.92, 1.1); bb.disk('grille', 'x', x+0.25, y0+0.56, z-0.05, 0.33, 0.02); bb.add('metalDark', new THREE.TorusGeometry(0.33, 0.018, 6, 28), x+0.26, y0+0.56, z-0.05, 0, Math.PI/2, 0); }
  else { bb.box('metal', x, y0+0.1, z, 1.1, 0.92, 0.48); bb.disk('grille', 'z', x-0.05, y0+0.56, z+0.25, 0.33, 0.02); bb.add('metalDark', new THREE.TorusGeometry(0.33, 0.018, 6, 28), x-0.05, y0+0.56, z+0.26); }
}
function homeBattery(bb, x, y0, z, n){
  for(let i=0;i<(n||1);i++){ const zz = z + i*0.82; bb.box('white', x, y0, zz, 0.22, 1.3, 0.7); bb.box('led', x+0.115, y0+0.42, zz, 0.01, 0.46, 0.035); }
}
/* Generic electric car (no brand styling), nose toward +z when ry = 0. Returns the charge port (local). */
function ev(bb, x, z, ry){
  const prof = (pts, depth, bevel) => {
    const sh = new THREE.Shape(); pts.forEach((p, i) => i ? sh.lineTo(p[0], p[1]) : sh.moveTo(p[0], p[1])); sh.closePath();
    const g = new THREE.ExtrudeGeometry(sh, { depth, bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 3, curveSegments: 4 });
    g.translate(0, 0, -depth/2); g.rotateY(-Math.PI/2); return g;
  };
  const r = R(bb, x, 0, z, ry);
  r.geo('carpaint', prof([[-2.28,0.34],[-2.3,0.9],[-2.02,1.02],[1.25,1.02],[2.16,0.84],[2.28,0.58],[2.22,0.34]], 1.7, 0.08), 0, 0, 0);
  r.geo('carglass', prof([[-1.96,1.0],[-1.48,1.44],[0.4,1.48],[1.2,1.0]], 1.38, 0.07), 0, 0, 0);
  r.geo('carpaint', prof([[-1.42,1.47],[0.32,1.5],[0.36,1.54],[-1.38,1.52]], 1.3, 0.04), 0, 0, 0);
  for(const [dx, dz] of [[-0.86,1.42],[0.86,1.42],[-0.86,-1.42],[0.86,-1.42]]){
    r.geo('dark', new THREE.CylinderGeometry(0.36, 0.36, 0.26, 24), dx, 0.36, dz, 0, Math.PI/2);
    r.geo('metal', new THREE.CylinderGeometry(0.21, 0.21, 0.27, 18), dx, 0.36, dz, 0, Math.PI/2);
  }
  r.box('lamp', 0, 0.74, 2.28, 1.4, 0.05, 0.04).box('tail', 0, 0.86, -2.33, 1.5, 0.07, 0.04);
  r.box('carpaint', -0.98, 0.98, 1.0, 0.18, 0.1, 0.22).box('carpaint', 0.98, 0.98, 1.0, 0.18, 0.1, 0.22);
  return [-0.93, 0.86, -1.85];
}
/* Bidirectional EV charger on a wall facing +x */
function evCharger(bb, x, y0, z, s){
  s = s || 1;
  bb.box('white', x+s*0.07, y0, z, 0.14, 0.55, 0.36);
  bb.box('led', x+s*0.145, y0+0.36, z, 0.01, 0.06, 0.2);
  bb.box('metalDark', x+s*0.1, y0-0.25, z, 0.06, 0.25, 0.06);
}
function rooftopUnit(bb, x, y0, z, w, d, h){
  bb.box('clay3', x, y0, z, w+0.3, 0.25, d+0.3);
  bb.box('metal', x, y0+0.25, z, w, h, d);
  const top = y0+0.25+h, nf = w > 2.4 ? 2 : 1;
  for(let i=0;i<nf;i++){ const fx = x + (nf===2 ? (i ? w/4 : -w/4) : 0); bb.cyl('grille', fx, top, z, Math.min(d, w/nf)*0.36, 0.06, 24); bb.add('metalDark', new THREE.TorusGeometry(Math.min(d, w/nf)*0.36, 0.03, 6, 28), fx, top+0.07, z, Math.PI/2); bb.cyl('metalDark', fx, top, z, 0.1, 0.1, 10); }
  for(let i=0;i<5;i++) bb.box('metalDark', x, y0+0.45+i*0.24, z+d/2+0.01, w-0.3, 0.05, 0.02);
}
function fence(bb, x0, z0, x1, z1, h){
  h = h || 1.9; const len = Math.hypot(x1-x0, z1-z0), n = Math.max(2, Math.round(len/2));
  for(let i=0;i<=n;i++){ const t = i/n; bb.box('metalDark', lerp(x0,x1,t), 0, lerp(z0,z1,t), 0.07, h, 0.07); }
  const nb = Math.round(len/0.16);
  for(let i=0;i<nb;i++){ const t = (i+0.5)/nb; bb.box('metal', lerp(x0,x1,t), 0.05, lerp(z0,z1,t), 0.018, h-0.12, 0.018); }
  bb.seg('metalDark', [x0, h-0.05, z0], [x1, h-0.05, z1], 0.05); bb.seg('metalDark', [x0, 0.12, z0], [x1, 0.12, z1], 0.04);
}
function meter(bb, x, y0, z, faceX){ faceX ? bb.box('metal', x, y0, z, 0.14, 0.55, 0.38) : bb.box('metal', x, y0, z, 0.38, 0.55, 0.14); }

/* =====================================================================
   BUILDINGS. Each returns { anchors, flows, svc } in local coordinates.
   anchors: named points for labels; flows: {id: [[x,y,z],...]}; svc: service point.
   ===================================================================== */
const BUILD = {};

/* Office complex, after HouseZero: 3 floors, wood fins over a glass front, roof PV, rooftop heat pumps, battery yard */
BUILD.office = function(bb){
  const FH = 4, NF = 3, H = NF*FH;
  bb.box('concrete', 1, 0, 0.3, 29, 0.18, 17.4);
  bb.box('clay', -11.5, 0.18, 0, 5, H+0.72, 16);
  bb.box('clay', 12.5, 0.18, 0, 3, H+0.72, 16);
  bb.box('clay', 1, 0.18, -7.6, 20, H-0.18, 0.8);
  for(let f=1;f<=NF;f++) bb.box('clay2', 1, f*FH-0.35, 0.25, 20.2, 0.4, 16.5);
  bb.box('clay', 1, H+0.05, 8.3, 20.2, 0.85, 0.4); bb.box('clay', 1, H+0.05, -7.8, 20.2, 0.85, 0.4);
  bb.box('trim', -11.5, H+0.9, 0, 5.1, 0.12, 16.1); bb.box('trim', 12.5, H+0.9, 0, 3.1, 0.12, 16.1); bb.box('trim', 1, H+0.9, 8.3, 20.2, 0.12, 0.45);
  const FS = FACE('z', 8), FE = FACE('x', 14);
  for(let f=0;f<NF;f++){
    const yF = f*FH + (f ? 0.05 : 0.18), y1 = (f+1)*FH - 0.35, zg = f ? 7.95 : 6.4;
    bb.box('glass', 1, yF, zg, 20, y1-yF, 0.05);
    for(let i=0;i<=10;i++) bb.box('metalDark', -9+i*2, yF, zg+0.04, 0.07, y1-yF, 0.12);
    bb.box('metalDark', 1, yF+(y1-yF)*0.8, zg+0.04, 20, 0.06, 0.12);
    bb.box('floor', 1, yF, -0.6, 19.8, 0.02, 13.6);
    for(let i=0;i<5;i++) bb.box('lamp', -7+i*4, y1-0.06, 1.5, 1.6, 0.05, 0.4);
    if(f){
      for(let i=0;i<5;i++) for(let j=0;j<2;j++){
        const x = -6.8+i*3.9, z = 0.6+j*3.4;
        table(bb, x, yF, z, 0, 1.6, 0.8, 0.74, 'clay2');
        bb.box('dark', x, yF+0.76, z-0.22, 0.6, 0.36, 0.04);
        chair(bb, x, yF, z+0.62, Math.PI, 'dark');
        if((i+j+f)%3 === 0) figure(bb, x, yF, z+0.62, Math.PI, 'sit');
      }
      bookshelf(bb, -6, yF, -6.6, 0, 3, 1.8, 3); bookshelf(bb, 4, yF, -6.6, 0, 3, 1.8, 3);
      potPlant(bb, 9.6, yF, 6.6, 1.2); potPlant(bb, -8.2, yF, 6.6, 1);
    } else {
      bb.box('wood', 3, yF, 1.5, 4.2, 1.05, 0.9); bb.box('clay2', 3, yF+1.05, 1.5, 4.4, 0.06, 1.0);
      figure(bb, 3.2, yF, 0.6, 0, 'stand'); figure(bb, 0.2, yF, 4.3, 2.4, 'walk'); figure(bb, -4.5, yF, 3.2, 0.6, 'stand'); figure(bb, -3.9, yF, 3.9, -2.4, 'stand');
      sofa(bb, -6, yF, -2.4, 0, 2.4); potPlant(bb, 8.8, yF, 5, 1.4); potPlant(bb, -8.4, yF, 5.4, 1.2);
    }
    win(bb, FE, -5.6, -3.6, f*FH+1.0, f*FH+3.1, { mull:1 }); win(bb, FE, -1.6, 0.4, f*FH+1.0, f*FH+3.1, { mull:1 });
    win(bb, FE, 2.4, 4.4, f*FH+1.0, f*FH+3.1, { mull:1 }); win(bb, FE, 5.6, 7.0, f*FH+1.0, f*FH+3.1, {});
    win(bb, FS, 11.7, 13.3, f*FH+1.0, f*FH+3.1, {});
    win(bb, FS, -13.4, -12.4, f*FH+0.8, f*FH+3.3, {}); win(bb, FS, -10.6, -9.6, f*FH+0.8, f*FH+3.3, {});
  }
  for(const x of [-8.6, -4.4, 1, 6, 10.4]) bb.box('clay', x, 0.18, 7.7, 0.45, 3.47, 0.45);
  for(let i=0;i<25;i++) bb.box('wood', -8.6+i*0.8, 4.05, 8.75, 0.1, 7.6, 0.5);
  // HouseZero-style solar chimney on the core
  bb.box('clay', -11.5, H+0.9, -3.5, 4.2, 3.6, 4.2);
  win(bb, FACE('z', -1.4), -13.2, -9.8, H+1.4, H+4.0, { mull:2, sill:false });
  bb.box('wood', -11.5, H+4.5, -3.5, 4.8, 0.28, 4.8);
  for(let i=0;i<6;i++) bb.box('wood', -11.5, H+4.0+0.08, -5.4+i*0.75, 4.4, 0.08, 0.12);
  bb.box('roof', 1, H+0.05, 0.25, 19.6, 0.02, 15.6);
  pvArray(bb, -8.4, -6.7, H+0.07, 8, 5, 1.85, 1.65, 0.12, 0.95, 12*DEG);
  for(const z of [-5.2, -1.4, 2.4]) rooftopUnit(bb, 9.3, H+0.05, z, 2.6, 2.2, 1.5);
  // battery yard
  bb.box('concrete', 19.2, 0, 1.4, 7, 0.2, 11.6);
  for(const z of [-1.6, 2.0]){
    bb.box('white', 19.2, 0.2, z, 2.3, 2.5, 3.0); bb.box('metalDark', 19.2, 2.7, z, 1.6, 0.12, 2.2);
    for(const dz of [-0.75, 0, 0.75]) bb.box('clay3', 20.36, 0.4, z+dz, 0.02, 2.1, 0.03);
    bb.box('led', 20.37, 0.7, z+1.15, 0.02, 1.4, 0.07);
  }
  bb.box('metal', 19.2, 0.2, 5.4, 1.8, 1.5, 1.6); for(let i=0;i<6;i++) bb.box('metalDark', 20.15, 0.3, 4.85+i*0.22, 0.12, 1.2, 0.05);
  fence(bb, 22.6, -4.2, 22.6, 7.2); fence(bb, 15.8, 7.2, 22.6, 7.2); fence(bb, 15.8, -4.2, 22.6, -4.2);
  meter(bb, 13.0, 0.9, 8.05, false);
  // plaza
  bb.box('concrete', 1, 0, 11.2, 30, 0.12, 5.6);
  for(const x of [-9, 5.5]){ bb.box('concrete', x, 0.12, 11.4, 4.2, 0.55, 1.4); bb.shrub(x-1.2, 0.67, 11.4, 0.7); bb.shrub(x, 0.67, 11.4, 0.75); bb.shrub(x+1.3, 0.67, 11.4, 0.65); }
  bb.box('wood', -2, 0.12, 12.2, 3.2, 0.45, 0.6); bb.box('wood', 10.5, 0.12, 12.2, 3.2, 0.45, 0.6);
  figure(bb, -2.6, 0.12, 12.4, Math.PI, 'sit'); figure(bb, 1.8, 0.12, 13.0, 1.4, 'walk'); figure(bb, 2.5, 0.12, 13.2, -1.6, 'stand');
  return {
    anchors:{ pv:[-0.5, 13.4, -1.5], hp:[9.3, 14.6, -1.4], battery:[19.2, 3.0, 0.2], building:[-1, 2.3, 9.2], facade:[-6, 9, 9.2], top:[0, 26, 0] },
    flows:{
      o_solar_bat:[[-0.5,13.05,0.5],[14.15,13.05,0.5],[14.15,1.3,0.5],[16.6,1.3,0.5],[16.6,1.3,-1.6],[18.0,1.3,-1.6]],
      o_bat_bldg:[[18.0,0.7,2.0],[14.15,0.7,2.0],[14.15,0.7,9.2],[-1,0.7,9.2],[-1,2.3,9.2]],
      o_solar_bldg:[[-1,13.05,1.5],[-1,13.05,9.2],[-1,2.3,9.2]]
    },
    svc:[13.0, 0.25, 8.6]
  };
};

/* Single-family home, modern: two volumes, cantilevered balcony, wood slats, cutaway living room, PV, two wall-mounted home batteries, heat pump */
BUILD.modernHome = function(bb){
  bb.box('concrete', 0, 0, 0.6, 14, 0.12, 11.6);
  bb.box('clay', -6.35, 0.12, 0, 0.3, 3.2, 10); bb.box('clay', 0, 0.12, -4.85, 13, 3.2, 0.3); bb.box('clay', 6.35, 0.12, 0, 0.3, 3.2, 10);
  bb.box('clay', 4.2, 0.12, 4.85, 4.3, 3.2, 0.3);
  for(let i=0;i<20;i++) bb.box('wood', 2.25+i*0.205, 0.12, 5.08, 0.12, 3.2, 0.12);
  bb.box('glass', -2, 0.12, 4.95, 8.4, 3.15, 0.04);
  for(const x of [-6.2, -4.1, -2, 0.1, 2.2]) bb.box('metalDark', x, 0.12, 4.98, 0.07, 3.15, 0.08);
  bb.box('metalDark', -2, 3.2, 4.98, 8.4, 0.07, 0.08);
  win(bb, FACE('x', 6.5), -3.4, -1.6, 0.9, 2.6, { mull:1 });
  // living room
  bb.box('floor', -2, 0.12, 0, 8.2, 0.02, 9.6);
  for(const x of [-5.85, 1.75]) for(let k=0;k<5;k++) bb.box('fabric', x + k*0.11, 0.14, 4.62 - (k%2)*0.08, 0.1, 3.0, 0.1);
  for(const x of [-5.85, 0.2]) for(let k=0;k<5;k++) bb.box('fabric', x + k*0.11, 3.66, 3.22 - (k%2)*0.08, 0.1, 3.0, 0.1);
  bb.box('fabric', -2.2, 0.14, 1.7, 3.4, 0.015, 2.4);
  sofa(bb, -2.2, 0.14, 0.4, 0, 2.7);
  figure(bb, -2.9, 0.14, 0.42, 0, 'sit');
  table(bb, -2.2, 0.14, 1.75, 0, 1.2, 0.6, 0.4, 'wood');
  bb.cyl('metalDark', -4.2, 0.14, -0.1, 0.02, 1.55, 8); bb.cyl('lamp', -4.2, 1.6, -0.1, 0.24, 0.32, 18, 0.16);
  potPlant(bb, -5.6, 0.14, 3.9, 1.3); potPlant(bb, 1.4, 0.14, 4.0, 1.0);
  bookshelf(bb, -6.0, 0.14, -1.4, Math.PI/2, 2.6, 2.3, 4);
  table(bb, 0.6, 0.14, -2.3, 0, 1.8, 0.9, 0.75, 'wood');
  for(const dx of [-0.5, 0.5]){ chair(bb, 0.6+dx, 0.14, -2.95, 0); chair(bb, 0.6+dx, 0.14, -1.65, Math.PI); }
  bb.cyl('metalDark', 0.6, 2.45, -2.3, 0.01, 0.9, 6); bb.cyl('lamp', 0.6, 2.25, -2.3, 0.28, 0.22, 18, 0.08);
  figure(bb, 1.5, 0.14, 2.4, -2.2, 'stand');
  // upper slab, balcony
  bb.box('clay2', 0, 3.32, 0.65, 13.6, 0.32, 11.3);
  bb.box('wood', -1.25, 3.64, 4.9, 10.7, 0.04, 2.6);
  bb.box('glass', -1.25, 3.68, 6.2, 10.7, 1.05, 0.03); bb.box('metal', -1.25, 4.72, 6.2, 10.7, 0.05, 0.07);
  bb.box('glass', -6.6, 3.68, 4.9, 0.03, 1.05, 2.6); bb.box('metal', -6.6, 4.72, 4.9, 0.07, 0.05, 2.6);
  R(bb, 2.6, 3.68, 4.9, -0.35).box('wood', 0, 0.2, 0.2, 0.72, 0.08, 1.4).box('fabric', 0, 0.28, 0.2, 0.68, 0.08, 1.3).box('fabric', 0, 0.42, -0.62, 0.68, 0.08, 0.75, -0.95);
  bb.cyl('wood', 1.6, 3.68, 5.2, 0.25, 0.45, 16);
  potPlant(bb, -5.8, 3.68, 5.6, 1.1);
  // upper volume
  bb.box('clay', -6.35, 3.64, -0.7, 0.3, 3.2, 8.6); bb.box('clay', -1.2, 3.64, -4.85, 10.6, 3.2, 0.3); bb.box('clay', 3.95, 3.64, -0.7, 0.3, 3.2, 8.6);
  bb.box('glass', -2.8, 3.64, 3.55, 6.8, 3.15, 0.04);
  for(const x of [-6.2, -3.9, -1.6, 0.6]) bb.box('metalDark', x, 3.64, 3.58, 0.07, 3.15, 0.08);
  bb.box('clay', 2.35, 3.64, 3.45, 3.5, 3.2, 0.3);
  for(let i=0;i<17;i++) bb.box('wood', 0.7+i*0.205, 3.64, 3.68, 0.12, 3.2, 0.12);
  win(bb, FACE('x', 4.1), -3.6, -1.4, 4.4, 6.2, { mull:1 });
  bb.box('floor', -2.8, 3.66, -0.6, 6.6, 0.02, 7.9);
  bb.box('fabric', -4.2, 3.66, -0.8, 1.9, 0.5, 2.1); bb.box('wood', -4.2, 3.66, -1.95, 2.0, 1.0, 0.12); bb.box('accent', -4.2, 4.16, -1.6, 1.6, 0.12, 0.4);
  bb.box('wood', -2.8, 3.66, -1.7, 0.5, 0.5, 0.45); bb.cyl('lamp', -2.8, 4.16, -1.7, 0.14, 0.24, 14, 0.1);
  table(bb, -0.6, 3.66, -3.6, 0, 1.4, 0.65, 0.74, 'wood'); figure(bb, -0.6, 3.66, -2.95, Math.PI, 'sit'); chair(bb, -0.6, 3.66, -2.95, Math.PI);
  // roof
  bb.box('clay2', -1.2, 6.84, -0.55, 11.6, 0.3, 9.9); bb.box('roof', -1.2, 7.14, -0.55, 11.2, 0.02, 9.5);
  bb.box('roof', 5.45, 3.64, 0.6, 2.5, 0.02, 11.0);
  pvArray(bb, -6.0, -4.9, 7.16, 6, 5, 1.65, 1.0, 0.08, 0.62, 5*DEG);
  // equipment
  homeBattery(bb, 6.61, 0.4, 1.4, 2);
  bb.box('white', 6.58, 1.25, 3.3, 0.15, 0.6, 0.45);
  heatPump(bb, 7.75, 0.12, -2.4, true);
  meter(bb, 6.57, 0.9, 4.3, true);
  // garden
  bb.box('grass', 0, 0, 8.4, 14.6, 0.05, 4.2);
  for(let i=0;i<5;i++) bb.box('concrete', 4.7, 0.05, 6.8+i*0.95, 1.2, 0.04, 0.6);
  bb.box('concrete', -4.4, 0.05, 7.4, 3.6, 0.55, 1.0); bb.shrub(-5.5, 0.6, 7.4, 0.6); bb.shrub(-4.4, 0.6, 7.4, 0.7); bb.shrub(-3.2, 0.6, 7.4, 0.55);
  bb.shrub(-6.8, 0.05, 9.6, 0.9); bb.shrub(1.2, 0.05, 9.4, 0.7); bb.shrub(6.8, 0.05, 8.2, 0.8);
  bb.box('lamp', 2.25, 1.9, 5.16, 0.1, 0.3, 0.06);
  return {
    anchors:{ pv:[-1, 8.0, -1.4], battery:[6.9, 1.9, 1.8], hp:[7.8, 1.4, -2.4], home:[-3, 1.7, 6.45], top:[0, 16, 0] },
    flows:{
      h7_solar_bat:[[-1,7.7,-1.5],[4.75,7.7,-1.5],[4.75,3.8,-1.5],[6.95,3.8,-1.5],[6.95,3.8,1.75],[6.95,1.8,1.75]],
      h7_solar_home:[[-3,7.7,0.5],[-3,7.7,4.6],[-3,3.8,4.6],[-3,3.8,6.45],[-3,1.7,6.45]],
      h7_bat_home:[[6.95,0.6,1.4],[6.95,0.6,6.45],[-3,0.6,6.45],[-3,1.7,6.45]],
      h7_hp:[[6.95,0.6,1.0],[6.95,0.6,-2.4],[7.45,0.6,-2.4]]
    },
    svc:[6.9, 0.25, 4.3]
  };
};

/* New England gable house (Cambridge two-family style), optional PV / home battery / heat pump */
BUILD.gableHouse = function(bb, o){
  o = o || {};
  const W = 9, D = 11, H = 6.0, RH = 4.0;
  bb.box('concrete', 0, 0, 0, W+0.4, 0.45, D+0.4);
  bb.box('clay', 0, 0.45, 0, W, H-0.45, D);
  const sh = new THREE.Shape(); sh.moveTo(-W/2, 0); sh.lineTo(W/2, 0); sh.lineTo(0, RH); sh.closePath();
  const pg = new THREE.ExtrudeGeometry(sh, { depth: D, bevelEnabled: false }); pg.translate(0, 0, -D/2);
  bb.add('clay', pg, 0, H, 0);
  const th = Math.atan2(RH, W/2), ov = 0.55, T = 0.2, L = Math.hypot(RH, W/2) + ov;
  for(const s of [-1, 1]){
    const ex = s*(W/2 + ov*Math.cos(th)), ey = H - ov*Math.sin(th), cx = ex/2, cy = (ey + H + RH)/2;
    bb.boxC('shingle', cx + s*Math.sin(th)*T/2, cy + Math.cos(th)*T/2, 0, L, T, D+0.9, 0, 0, -s*th);
    bb.boxC('trim', cx + s*Math.sin(th)*0.02, cy - Math.cos(th)*0.1, D/2+0.4, L, 0.3, 0.1, 0, 0, -s*th);
  }
  bb.boxC('trim', 0, H+RH+0.12, 0, 0.25, 0.12, D+0.9);
  for(const [x,z] of [[-1,1],[1,1],[1,-1]]) bb.box('trim', x*(W/2+0.02), 0.45, z*(D/2+0.02), 0.24, H-0.45, 0.24);
  bb.box('trim', 0, H-0.32, D/2+0.04, W, 0.32, 0.08); bb.box('trim', W/2+0.04, H-0.32, 0, 0.08, 0.32, D);
  bb.box('trim', 0, 0.45, D/2+0.03, W, 0.22, 0.08); bb.box('trim', W/2+0.03, 0.45, 0, 0.08, 0.22, D);
  const FS = FACE('z', D/2), FE = FACE('x', W/2);
  win(bb, FS, -3.4, -2.0, 1.1, 2.75, { mull:1, transom:0.55 }); win(bb, FS, 2.0, 3.4, 1.1, 2.75, { mull:1, transom:0.55 });
  bb.box('wood2', 0, 0.55, D/2+0.04, 1.0, 2.3, 0.08); bb.box('trim', 0, 2.85, D/2+0.06, 1.4, 0.16, 0.12);
  bb.box('trim', -0.6, 0.55, D/2+0.06, 0.14, 2.3, 0.12); bb.box('trim', 0.6, 0.55, D/2+0.06, 0.14, 2.3, 0.12);
  for(const [a,b] of [[-3.3,-2.1],[-0.6,0.6],[2.1,3.3]]) win(bb, FS, a, b, 3.6, 5.2, { mull:1, transom:0.5 });
  win(bb, FS, -0.45, 0.45, 6.7, 7.7, {});
  for(const z of [-3.6, -0.6, 2.6]){ win(bb, FE, z-0.6, z+0.6, 1.1, 2.75, { mull:1, transom:0.55 }); win(bb, FE, z-0.6, z+0.6, 3.6, 5.2, { mull:1, transom:0.5 }); }
  // porch
  bb.box('clay2', 0, 0, 6.65, 7.6, 0.55, 2.3);
  bb.box('concrete', 0, 0, 8.15, 1.6, 0.36, 0.7); bb.box('concrete', 0, 0, 8.55, 1.6, 0.18, 0.5);
  for(const x of [-3.55, -1.0, 1.0, 3.55]) bb.box('trim', x, 0.55, 7.6, 0.22, 2.55, 0.22);
  bb.boxC('shingle', 0, 3.3, 6.75, 8.2, 0.18, 2.7, 0.14);
  bb.box('trim', 0, 2.95, 7.95, 8.0, 0.24, 0.1);
  for(const [a,b] of [[-3.55,-1.0],[1.0,3.55]]){
    bb.box('trim', (a+b)/2, 1.45, 7.6, b-a, 0.07, 0.07); bb.box('trim', (a+b)/2, 0.65, 7.6, b-a, 0.06, 0.06);
    for(let u=a+0.2; u<b-0.1; u+=0.22) bb.box('trim', u, 0.65, 7.6, 0.04, 0.8, 0.04);
  }
  potPlant(bb, -2.4, 0.55, 6.4, 0.9);
  bb.box('wood', 2.4, 0.55, 6.0, 1.3, 0.45, 0.5);
  bb.box('brick', -2.2, H-0.5, -2.5, 0.9, 5.2, 0.9); bb.box('clay3', -2.2, H+4.7, -2.5, 1.05, 0.15, 1.05);
  bb.box('concrete', 0, 0, 10.0, 1.3, 0.05, 2.4);
  bb.shrub(-3.4, 0, 8.4, 0.7); bb.shrub(3.6, 0, 8.6, 0.6); bb.shrub(-4.6, 0, 7.6, 0.55);
  const anchors = { top:[0, 16, 0], house:[0, 3, 6.2] }, flows = {};
  if(o.pv){
    for(let r=0;r<2;r++) for(let c=0;c<8;c++){
      const dd = 1.2 + r*1.85, z = -4.2 + c*1.2;
      const px = Math.cos(th)*dd + Math.sin(th)*(T+0.07), py = H + RH - Math.sin(th)*dd + Math.cos(th)*(T+0.07);
      bb.boxC('pv', px, py, z, 1.75, 0.045, 1.12, 0, 0, -th);
    }
    anchors.pv = [2.6, 9.0, 0];
  }
  if(o.battery){
    homeBattery(bb, W/2+0.12, 0.6, -2.2, 1); anchors.battery = [W/2+0.3, 2.1, -2.2];
    flows[o.batFlow] = [[W/2+0.35,0.7,-2.2],[W/2+0.35,0.7,3.8],[W/2+0.35,2.2,3.8]];
  }
  if(o.hp){ heatPump(bb, W/2+1.2, 0, -2.4, true); anchors.hp = [W/2+1.3, 1.4, -2.4]; }
  if(o.ev){
    const cx = -(W/2+1.55), cz = 3.4, cz0 = 4.7;
    bb.box('concrete', cx, 0, 6.2, 2.9, 0.06, 12.2);
    evCharger(bb, -W/2, 0.95, cz0, -1);
    const port = ev(bb, cx, cz, Math.PI), pw = [cx - port[0], port[1], cz - port[2]];
    bb.seg('dark', [-W/2-0.17, 0.7, cz0], [(pw[0]-W/2)/2, 0.35, (cz0+pw[2])/2], 0.035); bb.seg('dark', [(pw[0]-W/2)/2, 0.35, (cz0+pw[2])/2], pw, 0.035);
    anchors.ev = [cx, 1.7, cz]; anchors.charger = [-W/2-0.2, 1.3, cz0];
    flows[o.evFlow] = [[pw[0], 0.95, pw[2]], [-W/2-0.3, 0.95, pw[2]], [-W/2-0.3, 0.95, 2.0], [-W/2-0.3, 2.2, 2.0]];
  }
  meter(bb, W/2+0.08, 0.95, 4.6, true);
  return { anchors, flows, svc:[W/2+0.35, 0.25, 4.6] };
};

/* Corner café: brick two-story, storefront cutaway, awning, sidewalk tables, rooftop unit, walk-in cooler */
BUILD.cafe = function(bb){
  bb.box('concrete', 0, 0, 0, 14.4, 0.15, 10.4);
  bb.box('brick', -6.8, 0.15, 0, 0.4, 4.05, 10); bb.box('brick', 6.8, 0.15, 0, 0.4, 4.05, 10); bb.box('brick', 0, 0.15, -4.8, 13.2, 4.05, 0.4);
  bb.box('brick', -6.75, 0.15, 4.85, 0.55, 4.05, 0.55); bb.box('brick', 6.75, 0.15, 4.85, 0.55, 4.05, 0.55);
  bb.box('clay2', -3.6, 0.15, 4.88, 5.8, 0.45, 0.22); bb.box('clay2', 3.6, 0.15, 4.88, 5.8, 0.45, 0.22);
  bb.box('glass', -3.6, 0.6, 4.92, 5.8, 3.0, 0.04); bb.box('glass', 3.6, 0.6, 4.92, 5.8, 3.0, 0.04);
  bb.box('glass', 0, 0.15, 4.92, 1.4, 2.6, 0.04); bb.box('glass', 0, 2.8, 4.92, 1.4, 0.8, 0.04);
  for(const x of [-6.45, -4.55, -2.6, -0.72, 0.72, 2.6, 4.55, 6.45]) bb.box('awning', x, 0.15, 4.96, 0.1, 3.45, 0.12);
  bb.box('awning', 0, 2.72, 4.96, 13, 0.09, 0.12); bb.box('awning', 0, 3.55, 4.96, 13, 0.08, 0.12);
  bb.box('trim', 0, 3.6, 5.0, 14.0, 0.62, 0.26); bb.box('dark', 0, 3.72, 5.14, 3.4, 0.38, 0.02);
  for(let i=0;i<12;i++) bb.boxC(i%2 ? 'fabric' : 'awning', -6.05+i*1.1, 3.32, 5.95, 1.1, 0.04, 1.95, 0.38);
  bb.box('awning', 0, 2.82, 6.85, 13.2, 0.26, 0.03);
  // upper floor
  bb.box('trim', 0, 4.15, 0, 14.3, 0.14, 10.3);
  bb.box('brick', 0, 4.25, 0, 14, 3.35, 10);
  const FS = FACE('z', 5), FE = FACE('x', 7);
  for(const u of [-5, -1.8, 1.8, 5]) win(bb, FS, u-0.72, u+0.72, 4.85, 6.85, { mull:1, transom:0.62, lintel:'trim' });
  for(const z of [-3, 0, 3]) win(bb, FE, z-0.72, z+0.72, 4.85, 6.85, { mull:1, transom:0.62, lintel:'trim' });
  win(bb, FE, 1.0, 2.6, 1.0, 3.1, { mull:1 });
  bb.box('trim', 0, 7.6, 0, 14.5, 0.3, 10.5); bb.box('trim', 0, 7.9, 0, 14.2, 0.22, 10.2); bb.box('roof', 0, 8.12, 0, 13.6, 0.02, 9.6);
  // interior
  bb.box('floor', 0, 0.15, 0, 13.2, 0.02, 9.2);
  bb.box('wood', 2.5, 0.17, -1.8, 5, 1.0, 0.8); bb.box('clay2', 2.5, 1.17, -1.8, 5.2, 0.06, 0.95);
  bb.box('metal', 1.4, 1.23, -2.0, 0.8, 0.45, 0.5); bb.box('dark', 0.6, 1.23, -2.0, 0.25, 0.5, 0.25);
  bb.box('glass', 4.1, 1.23, -1.65, 1.6, 0.45, 0.6); bb.box('book3', 4.1, 1.25, -1.65, 1.4, 0.12, 0.45);
  for(let l=0;l<3;l++){ bb.box('wood', 2.5, 1.4+l*0.5, -4.45, 5, 0.04, 0.3); for(let i=0;i<9;i++) bb.cyl(['book1','book2','book3','book4'][(i+l)%4], 0.4+i*0.5, 1.44+l*0.5, -4.45, 0.09, 0.22, 10); }
  bb.box('dark', 2.5, 2.55, -4.58, 3.2, 0.95, 0.03);
  for(const x of [0.8, 2.5, 4.2]){ bb.cyl('metalDark', x, 2.6, -1.6, 0.008, 1.42, 6); bb.cyl('lamp', x, 2.38, -1.6, 0.2, 0.24, 16, 0.06); }
  for(const [x,z] of [[-4.6,1.4],[-2.0,2.7],[-4.8,-1.6],[-1.6,-0.4]]){
    roundTable(bb, x, 0.17, z); chair(bb, x-0.6, 0.17, z, Math.PI/2); chair(bb, x+0.6, 0.17, z, -Math.PI/2);
  }
  figure(bb, -5.2, 0.17, 1.4, Math.PI/2, 'sit'); figure(bb, -1.4, 0.17, 2.7, -Math.PI/2, 'sit'); figure(bb, -5.4, 0.17, -1.6, Math.PI/2, 'sit');
  figure(bb, 2.5, 0.17, -2.65, 0, 'stand'); figure(bb, 1.2, 0.17, -0.7, Math.PI, 'stand'); figure(bb, 0.4, 0.17, 0.2, Math.PI-0.4, 'stand');
  // roof
  rooftopUnit(bb, -2.2, 8.12, -1.6, 3.4, 2.3, 1.45);
  bb.box('metal', 2.6, 8.12, -2.5, 0.6, 0.6, 3.4);
  // walk-in cooler
  bb.box('clay2', 8.8, 0.15, -2.6, 3.6, 3.0, 4.4);
  for(const z of [-3.9, -2.6, -1.3]) bb.box('clay3', 10.61, 0.3, z, 0.02, 2.7, 0.04);
  for(const x of [7.6, 10.0]) bb.box('clay3', x, 0.3, -0.39, 0.04, 2.7, 0.02);
  bb.box('metal', 8.8, 0.2, -0.37, 1.0, 2.1, 0.05); bb.box('metalDark', 9.15, 1.1, -0.32, 0.05, 0.3, 0.05);
  bb.box('metal', 8.8, 3.15, -2.6, 1.6, 0.8, 1.1); bb.disk('grille', 'x', 9.62, 3.55, -2.6, 0.3, 0.03);
  meter(bb, 7.07, 0.9, 4.4, true);
  // sidewalk seating
  for(const x of [-4.8, -1.8, 4.6]){ roundTable(bb, x, 0.15, 7.7, 0.4); chair(bb, x-0.62, 0.15, 7.7, Math.PI/2, 'metalDark'); chair(bb, x+0.62, 0.15, 7.7, -Math.PI/2, 'metalDark'); }
  figure(bb, -5.42, 0.15, 7.7, Math.PI/2, 'sit'); figure(bb, 5.22, 0.15, 7.7, -Math.PI/2, 'sit');
  bb.cyl('metalDark', 4.6, 0.86, 7.7, 0.03, 1.6, 8); bb.cyl('fabric', 4.6, 2.3, 7.7, 1.45, 0.45, 20, 0.05);
  bb.box('wood2', -6.6, 0.15, 7.7, 0.8, 0.5, 1.6); bb.shrub(-6.6, 0.65, 7.7, 0.55);
  R(bb, 1.3, 0.15, 7.6, 0.3).box('dark', 0, 0, 0, 0.6, 0.9, 0.04, 0.18).box('dark', 0, 0, 0.3, 0.6, 0.9, 0.04, -0.18);
  return {
    anchors:{ hvac:[-2.2, 10.0, -1.6], cooler:[10.7, 2.5, -2.6], cafe:[-4, 2.4, 5.4], top:[0, 16, 0] },
    flows:{
      c_cooler:[[7.4,0.8,4.4],[7.4,0.8,-0.15],[7.7,0.8,-0.15],[7.7,1.8,-0.15]],
      c_hvac:[[7.4,0.8,4.0],[7.4,8.35,4.0],[-2.2,8.35,4.0],[-2.2,8.35,-0.25],[-2.2,9.1,-0.25]]
    },
    svc:[7.4, 0.25, 4.6]
  };
};

/* Public library: double-height reading hall behind white fins, low wing, roof PV, rooftop HVAC, shared battery yard */
BUILD.library = function(bb){
  bb.box('concrete', 0, 0, 0, 33, 0.25, 19);
  bb.box('clay', -15.8, 0.25, 0, 0.4, 9.25, 18); bb.box('clay', -7, 0.25, -8.8, 18, 9.25, 0.4);
  bb.box('glass', -7, 0.25, 8.6, 17.6, 9.0, 0.05);
  for(let i=0;i<12;i++) bb.box('clay', -15.6+i*1.6, 0.25, 9.15, 0.35, 9.3, 1.1);
  bb.box('metalDark', -7, 4.7, 8.64, 17.6, 0.08, 0.08);
  bb.box('floor', -7, 0.25, 0, 17.4, 0.02, 17.4);
  bb.box('clay2', -7, 4.6, -4.6, 17.4, 0.3, 8.2);
  bb.box('glass', -7, 4.9, -0.45, 17.4, 1.0, 0.03); bb.box('metal', -7, 5.88, -0.45, 17.4, 0.05, 0.06);
  for(let r=0;r<3;r++) for(let s=0;s<4;s++) bookshelf(bb, -13.2+s*3.8, 0.27, -7.4+r*2.1, 0, 3.4, 2.1, 4);
  for(let s=0;s<5;s++) bookshelf(bb, -14+s*3.5, 4.9, -8.3, 0, 3.3, 2.4, 5);
  for(const z of [2.4, 5.6]) for(const x of [-12.5, -7.5, -2.5]){
    table(bb, x, 0.27, z, 0, 3.0, 1.1, 0.76, 'wood');
    for(const dx of [-0.9, 0, 0.9]){ chair(bb, x+dx, 0.27, z-0.8, 0); chair(bb, x+dx, 0.27, z+0.8, Math.PI); }
    bb.box('lamp', x-0.6, 1.03, z, 0.3, 0.12, 0.2); bb.box('lamp', x+0.6, 1.03, z, 0.3, 0.12, 0.2);
  }
  figure(bb, -12.5, 0.27, 1.6, 0, 'sit'); figure(bb, -6.6, 0.27, 6.4, Math.PI, 'sit'); figure(bb, -3.4, 0.27, 1.6, 0, 'sit'); figure(bb, -8.4, 0.27, 4.8, 0, 'sit');
  figure(bb, -10, 0.27, -1.4, 0.4, 'stand'); figure(bb, -1, 0.27, 7.4, 2.6, 'walk'); figure(bb, -9, 4.9, -3, 0.2, 'stand');
  for(const z of [-5, 0, 5]) bb.box('lamp', -7, 8.9, z, 15, 0.06, 0.25);
  potPlant(bb, -14.6, 0.27, 7.6, 1.4); potPlant(bb, 0.6, 0.27, 7.6, 1.4);
  bb.box('clay2', -7, 9.5, 0.25, 18.8, 0.55, 19.3); bb.box('roof', -7, 10.05, 0.25, 18.4, 0.02, 18.9);
  // low wing
  bb.box('clay', 9, 0.25, 0, 14, 5.25, 18);
  win(bb, FACE('z', 9), 7.0, 15.4, 1.2, 3.9, { mull:6 });
  win(bb, FACE('x', 16), -7.5, 7.5, 1.2, 3.9, { mull:9 });
  win(bb, FACE('z', 9), 2.6, 5.6, 0.3, 3.5, { mull:2, sill:false, transom:0.78, frameMat:'metalDark' });
  bb.box('clay2', 9, 5.5, 0, 14.6, 0.4, 18.6); bb.box('roof', 9, 5.9, 0, 14.2, 0.02, 18.2);
  bb.box('clay2', 4.2, 4.0, 10.6, 8.2, 0.28, 3.4); bb.box('metal', 1.2, 0.25, 12.0, 0.14, 3.75, 0.14); bb.box('metal', 7.2, 0.25, 12.0, 0.14, 3.75, 0.14);
  bb.box('concrete', 4.2, 0, 10.25, 7, 0.17, 1.5);
  // roof PV and HVAC
  pvArray(bb, -15.4, -8.2, 10.07, 8, 5, 1.85, 1.7, 0.1, 1.3, 12*DEG);
  pvArray(bb, 3.0, -7.8, 5.92, 4, 5, 1.85, 1.6, 0.1, 1.2, 12*DEG);
  rooftopUnit(bb, 13.6, 5.9, -5.2, 3.0, 2.3, 1.4); rooftopUnit(bb, 13.6, 5.9, 0.4, 3.0, 2.3, 1.4);
  // shared community battery
  bb.box('concrete', 22, 0, 0, 8, 0.2, 13);
  for(const z of [-2.9, 2.9]){
    bb.box('white', 21.8, 0.2, z, 2.6, 2.8, 5.2);
    for(let k=0;k<13;k++) bb.box('clay2', 23.12, 0.35, z-2.4+k*0.4, 0.04, 2.5, 0.09);
    bb.box('led', 23.14, 0.7, z+2.1, 0.02, 1.5, 0.08);
    bb.box('metal', 21.8, 3.0, z, 1.4, 0.4, 1.8);
  }
  bb.box('led', 21.8, 0.7, 5.51, 1.8, 0.05, 0.02);
  fence(bb, 25.8, -6.3, 25.8, 6.3); fence(bb, 18.2, 6.3, 25.8, 6.3); fence(bb, 18.2, -6.3, 25.8, -6.3);
  meter(bb, 16.09, 0.9, 8.6, true);
  // site
  bb.box('grass', -7, 0, 12.6, 19, 0.05, 6);
  bb.cyl('metal', -15, 0.05, 13.4, 0.07, 11, 8); bb.box('awning', -14.45, 9.2, 13.4, 1.0, 0.65, 0.03);
  for(let i=0;i<5;i++) bb.add('metalDark', new THREE.TorusGeometry(0.4, 0.03, 6, 16, Math.PI), 9.5+i*0.7, 0.25, 11.5, 0, Math.PI/2, 0);
  bb.box('wood', -4, 0.05, 13.8, 3, 0.45, 0.6); bb.box('wood', -10, 0.05, 13.8, 3, 0.45, 0.6);
  figure(bb, -4.4, 0.05, 13.9, Math.PI, 'sit'); figure(bb, 3.6, 0.25, 12.6, 0.3, 'walk'); figure(bb, 8.2, 0.05, 13.6, -1.2, 'walk');
  bb.shrub(-14.5, 0.05, 10.5, 0.9); bb.shrub(-11, 0.05, 10.6, 0.8); bb.shrub(0.2, 0.05, 10.5, 0.85);
  return {
    anchors:{ pv:[-6, 11.4, -1], hvac:[13.6, 8.2, -2.4], battery:[21.8, 3.7, 0], library:[-9, 6.5, 10.2], top:[-4, 22, 0] },
    flows:{
      l_solar_bat:[[7,6.85,-1],[16.25,6.85,-1],[16.25,1.2,-1],[20.4,1.2,-1]],
      l_bat_lib:[[20.4,0.6,2.9],[16.25,0.6,2.9],[16.25,0.6,10.05],[-4,0.6,10.05],[-4,1.8,10.05]],
      l_solar_lib:[[-6,10.95,-1],[-6,10.95,10.05],[-6,1.8,10.05],[-4,1.8,10.05]]
    },
    svc:[16.35, 0.25, 9.3]
  };
};

/* Lattice transmission tower. Returns conductor attach points in local coords (x across the line). */
BUILD.tower = function(bb, H){
  H = H || 34; const ht = H-7, wb = 3.4, wt = 0.9;
  const w = y => wb + (wt-wb)*y/ht;
  const lv = [0, 5, 10, 14.5, 19, 23, ht];
  const C = [[-1,-1],[1,-1],[1,1],[-1,1]];
  for(const [a,b] of C) bb.seg('metalDark', [a*wb,0,b*wb], [a*wt,ht,b*wt], 0.16);
  for(let i=0;i<lv.length;i++){
    const y = lv[i], q = w(y);
    for(let k=0;k<4;k++){ const p = C[k], n = C[(k+1)%4]; bb.seg('metalDark', [p[0]*q,y,p[1]*q], [n[0]*q,y,n[1]*q], 0.09); }
    if(i < lv.length-1){ const y2 = lv[i+1], q2 = w(y2);
      for(let k=0;k<4;k++){ const p = C[k], n = C[(k+1)%4];
        bb.seg('metalDark', [p[0]*q,y,p[1]*q], [n[0]*q2,y2,n[1]*q2], 0.06); bb.seg('metalDark', [n[0]*q,y,n[1]*q], [p[0]*q2,y2,p[1]*q2], 0.06); } }
  }
  for(const [a,b] of C) bb.seg('metalDark', [a*wt,ht,b*wt], [0,H,0], 0.12);
  const att = [];
  for(const [y, arm] of [[ht-1, 7.5], [ht+3.2, 5.2]]){
    for(const s of [-1, 1]){
      bb.seg('metalDark', [s*wt, y, -wt], [s*arm, y, 0], 0.1); bb.seg('metalDark', [s*wt, y, wt], [s*arm, y, 0], 0.1);
      bb.seg('metalDark', [s*wt, y-2.4, 0], [s*arm, y, 0], 0.07);
      bb.seg('clay2', [s*arm, y, 0], [s*arm, y-1.8, 0], 0.22);
      att.push([s*arm, y-1.8, 0]);
    }
  }
  return att;
};

/* Power plant with hyperbolic cooling towers. Returns smoke source points (local). */
BUILD.plant = function(bb){
  const towers = [[-22,-6,36],[8,-18,39],[30,6,34]], tops = [];
  for(const [x,z,H] of towers){
    const pts = [], a = H*0.2, b = H*0.48, y0 = H*0.74;
    for(let i=0;i<=24;i++){ const y = i/24*H; pts.push(new THREE.Vector2(a*Math.sqrt(1+((y-y0)/b)**2), y)); }
    bb.add('clay', new THREE.LatheGeometry(pts, 48), x, 0, z);
    const rt = pts[24].x;
    bb.add('clay2', new THREE.TorusGeometry(rt, 0.35, 8, 48), x, H, z, Math.PI/2);
    bb.cyl('dark', x, H-1.8, z, rt*0.96, 0.1, 40);
    bb.cyl('clay3', x, 0, z, pts[0].x+0.3, 1.2, 48);
    tops.push([x, H+1, z]);
  }
  bb.box('clay', 2, 0, 22, 36, 18, 16); bb.box('clay2', 2, 18, 22, 37, 1.0, 17);
  for(let i=0;i<8;i++) win(bb, FACE('z', 30), -14+i*4.2, -12+i*4.2, 6, 15, { mull:2, sill:false });
  bb.cyl('clay2', 24, 0, 18, 2.4, 48, 24, 1.9); bb.cyl('clay3', 24, 43, 18, 2.0, 2.0, 24);
  bb.box('concrete', 0, 0, 10, 90, 0.2, 70);
  return tops;
};

/* Substation: transformers, gantry, fence */
BUILD.substation = function(bb){
  bb.box('concrete', 0, 0, 0, 16, 0.2, 12);
  for(const x of [-3.5, 3.5]){
    bb.box('metal', x, 0.2, 0.5, 2.8, 2.6, 2.2);
    for(let i=0;i<7;i++) bb.box('metalDark', x-1.2+i*0.4, 0.5, 1.68, 0.06, 2.0, 0.18);
    for(const dx of [-0.8, 0, 0.8]){ bb.cyl('clay2', x+dx, 2.8, 0.2, 0.12, 1.2, 10); for(let k=0;k<4;k++) bb.cyl('clay2', x+dx, 3.0+k*0.25, 0.2, 0.2, 0.06, 12); }
  }
  for(const x of [-6.5, 6.5]){ bb.cyl('metal', x, 0.2, -3.2, 0.22, 10, 10); }
  bb.box('metal', 0, 9.6, -3.2, 13.6, 0.5, 0.5);
  for(const x of [-4, 0, 4]) bb.seg('clay2', [x, 9.6, -3.2], [x, 8.2, -3.2], 0.25);
  fence(bb, -8, -6, 8, -6, 2.4); fence(bb, -8, 6, 8, 6, 2.4); fence(bb, -8, -6, -8, 6, 2.4); fence(bb, 8, -6, 8, 6, 2.4);
  return { anchors:{ top:[0, 26, 0], gantry:[0, 9.6, -3.2] } };
};

/* =====================================================================
   STAGE: renderer, lighting, camera rig, flows, moods, smoke, export
   ===================================================================== */
const MOOD = {
  day:     { bg:'#dcdddc', sun:3.5, sunC:'#fffaf4', hemi:0.42, sky:'#eef2f8', gnd:'#c6c3bb', env:0.28, room:0.14, roomDim:0.05, lamp:0.9, glass:0.3, street:0.0, track:0.5, smoke:'#d9dbdd', exp:0.9 },
  evening: { bg:'#121417', sun:0.16, sunC:'#8fa6d4', hemi:0.11, sky:'#7d8fae', gnd:'#121417', env:0.045, room:2.4, roomDim:0.5, lamp:4.0, glass:0.55, street:0.8, track:0.22, smoke:'#80868e', exp:1.05 }
};
const KIND_W = { strain:4.6, solar:3.8, battery:3.8, grid:3.4, signal:3.4 };
const KIND_V = { strain:3.0, solar:1.45, battery:1.3, grid:1.3, signal:1.3 };

function createStage(canvas, opts){
  opts = opts || {};
  const W = 1600, H = 900;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: opts.ao === false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setSize(W, H, false);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap; renderer.shadowMap.autoUpdate = false;
  let shadowDirty = true;
  renderer.toneMapping = THREE.NeutralToneMapping; renderer.toneMappingExposure = 1.0;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(MOOD.day.bg);
  scene.fog = new THREE.Fog(MOOD.day.bg, 380, 1100);
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new X.RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = MOOD.day.env;

  const camera = new THREE.PerspectiveCamera(26, W/H, 2, 4000);
  const hemi = new THREE.HemisphereLight(MOOD.day.sky, MOOD.day.gnd, MOOD.day.hemi); scene.add(hemi);
  const sun = new THREE.DirectionalLight(MOOD.day.sunC, MOOD.day.sun);
  sun.castShadow = true; sun.shadow.mapSize.set(4096, 4096); sun.shadow.bias = -0.0003; sun.shadow.normalBias = 0.035;
  sun.shadow.camera.near = 1; sun.shadow.camera.far = 1400;
  scene.add(sun, sun.target);
  const SUN_DIR = V3(-0.66, 0.54, 0.4).normalize(), sunOff = V3(0,0,0), _sd = V3(0,0,0);

  const world = new THREE.Group(); world.name = 'commonwatt-world'; scene.add(world);
  const fx = new THREE.Group(); fx.name = 'commonwatt-fx'; scene.add(fx);
  const noAO = [fx];

  /* post: GTAO ambient occlusion */
  let composer = null, gtao = null;
  if(opts.ao !== false){
    const rt = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 4 });
    composer = new X.EffectComposer(renderer, rt);
    composer.addPass(new X.RenderPass(scene, camera));
    gtao = new X.GTAOPass(scene, camera, W, H);
    gtao.updateGtaoMaterial({ radius: 3, distanceExponent: 1.3, thickness: 3, scale: 1.5, samples: 12 });
    gtao.updatePdMaterial({ lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 4, rings: 2, samples: 8 });
    gtao.blendIntensity = 1.0;
    const r0 = gtao.render.bind(gtao);
    gtao.render = function(){ const hidden = []; scene.traverse(o => { if((o.userData.noAO || noAO.includes(o)) && o.visible){ o.visible = false; hidden.push(o); } }); r0.apply(null, arguments); hidden.forEach(o => o.visible = true); };
    composer.addPass(gtao);
    composer.addPass(new X.OutputPass());
  }
  let pr = 1;
  function setPixelRatio(p){ pr = p; renderer.setPixelRatio(p); if(composer){ composer.setPixelRatio(p); composer.setSize(W, H); } }
  setPixelRatio(Math.min(1.5, window.devicePixelRatio || 1));

  /* ---------- buildings ---------- */
  const B = {};
  const leaves = [];
  function place(key, wx, wz, fn, arg, seed, ry){
    ry = ry || 0;
    const bb = new Builder(seed || key.length*31+7);
    const info = fn(bb, arg) || {};
    const grp = bb.build(key); grp.position.set(wx, 0, wz); grp.rotation.y = ry; grp.updateMatrixWorld(); world.add(grp);
    const c = Math.cos(ry), s = Math.sin(ry);
    const toW = p => V3(wx + p[0]*c + p[2]*s, p[1], wz - p[0]*s + p[2]*c);
    bb.leaves.forEach(l => { const w = toW([l.x, l.y, l.z]); leaves.push({ x:w.x, y:l.y, z:w.z, r:l.r, c:l.c }); });
    const b = { key, x:wx, z:wz, ry, toW, group:grp, anchors:{}, svc:null, info };
    for(const k in info.anchors || {}) b.anchors[k] = toW(info.anchors[k]);
    if(info.svc) b.svc = toW(info.svc);
    for(const id in info.flows || {}) addFlow(id, info.flows[id].map(toW));
    B[key] = b; return b;
  }
  function finishLeaves(){
    if(!leaves.length) return;
    const geo = new THREE.IcosahedronGeometry(1, 0);
    const im = new THREE.InstancedMesh(geo, leafMat, leaves.length);
    const m = new THREE.Matrix4(), c = new THREE.Color();
    leaves.forEach((l, i) => { m.makeScale(l.r, l.r*0.92, l.r); m.setPosition(l.x, l.y, l.z); im.setMatrixAt(i, m); im.setColorAt(i, c.set(l.c)); });
    im.castShadow = true; im.receiveShadow = true; im.name = 'foliage';
    world.add(im); leaves.length = 0;
  }

  /* ---------- energy flows ---------- */
  const F = {};
  const trackMat = new X.LineMaterial({ color: '#c9ccc8', linewidth: 1.4, transparent: true, opacity: MOOD.day.track, depthWrite: false });
  const lineMats = [trackMat];
  const dotGeo = new THREE.SphereGeometry(1, 16, 12);
  function addFlow(id, pts, opt){
    opt = opt || {};
    const pos = []; pts.forEach(p => pos.push(p.x, p.y, p.z));
    const geo = new X.LineGeometry(); geo.setPositions(pos);
    const mk = o => { const m = new X.LineMaterial(Object.assign({ color:'#ffffff', linewidth:3, transparent:true, opacity:0, depthWrite:false }, o)); lineMats.push(m); return m; };
    const track = new X.Line2(geo, opt.trackMat || trackMat);
    const glow = new X.Line2(geo, mk({ linewidth: 11 }));
    const base = new X.Line2(geo, mk({ linewidth: 3 }));
    const dash = new X.Line2(geo, mk({ linewidth: 3.6, dashed: true, dashSize: 0.45, gapSize: 0.8 }));
    dash.computeLineDistances();
    const g = new THREE.Group(); g.name = 'flow:'+id;
    if(!opt.noTrack) g.add(track);
    g.add(glow, base, dash);
    const dotMat = new THREE.MeshBasicMaterial({ color:'#ffffff', transparent:true, opacity:0, depthWrite:false });
    const dots = [pts[0], pts[pts.length-1]].map(p => { const d = new THREE.Mesh(dotGeo, dotMat); d.position.copy(p); g.add(d); return d; });
    glow.renderOrder = 2; base.renderOrder = 3; dash.renderOrder = 4;
    fx.add(g);
    let len = 0; for(let i=1;i<pts.length;i++) len += pts[i].distanceTo(pts[i-1]);
    F[id] = { id, pts, g, glow, base, dash, dots, dotMat, kind:null, speed:1, off:Math.random()*4, o:0, target:0, len };
    return F[id];
  }
  function setFlow(id, kind, speed){
    const f = F[id]; if(!f) return;
    f.speed = speed == null ? 1 : speed;
    if(kind){
      f.kind = kind; f.target = 1;
      const col = PAL[kind] || kind;
      f.glow.material.color.set(col); f.base.material.color.set(col); f.dotMat.color.set(col);
      f.dash.material.color.set(col).lerp(new THREE.Color('#ffffff'), 0.6);
    } else f.target = 0;
  }
  function allFlowsOff(){ for(const id in F) F[id].target = 0; }
  function addWire(pts, color){
    const pos = []; pts.forEach(p => pos.push(p.x, p.y, p.z));
    const geo = new X.LineGeometry(); geo.setPositions(pos);
    const m = new X.LineMaterial({ color: color || PAL.wire, linewidth: 1.2, transparent: true, opacity: 0.85, depthWrite: false });
    lineMats.push(m); const l = new X.Line2(geo, m); fx.add(l); return l;
  }
  function catenary(a, b, sag, n){ const out = []; n = n || 14; for(let i=0;i<=n;i++){ const t = i/n; out.push(V3(lerp(a.x,b.x,t), lerp(a.y,b.y,t) - sag*4*t*(1-t), lerp(a.z,b.z,t))); } return out; }

  /* ---------- street lamps and ground glow ---------- */
  const glowMat = new THREE.MeshBasicMaterial({ map: radialTex, color:'#ffcf8a', transparent:true, opacity:0, depthWrite:false, blending: THREE.AdditiveBlending });
  const glowGeo = new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI/2);
  function groundGlow(x, z, r){ const m = new THREE.Mesh(glowGeo, glowMat); m.scale.set(r, 1, r); m.position.set(x, 0.18, z); fx.add(m); }

  /* ---------- smoke ---------- */
  const smokeMat = new THREE.SpriteMaterial({ map: radialTex, color: MOOD.day.smoke, transparent: true, opacity: 0, depthWrite: false });
  const puffs = [];
  let smokeLevel = 0.75, smokeTarget = 0.75;
  const smokeSources = [];
  function addSmoke(p){ smokeSources.push(p.clone()); for(let i=0;i<7;i++){ const s = new THREE.Sprite(smokeMat.clone()); fx.add(s); puffs.push({ s, src:p.clone(), ph: i/7*6 + Math.random()*0.4 }); } }

  /* ---------- mood ---------- */
  let mood = 0, moodTarget = 0;
  const _c0 = new THREE.Color(), _c1 = new THREE.Color();
  function lerpC(target, a, b, t){ target.copy(_c0.set(a)).lerp(_c1.set(b), t); }
  function applyMood(){
    const a = MOOD.day, b = MOOD.evening, t = mood;
    lerpC(scene.background, a.bg, b.bg, t); scene.fog.color.copy(scene.background);
    sun.intensity = lerp(a.sun, b.sun, t); lerpC(sun.color, a.sunC, b.sunC, t);
    hemi.intensity = lerp(a.hemi, b.hemi, t); lerpC(hemi.color, a.sky, b.sky, t); lerpC(hemi.groundColor, a.gnd, b.gnd, t);
    scene.environmentIntensity = lerp(a.env, b.env, t); renderer.toneMappingExposure = lerp(a.exp, b.exp, t);
    MAT.room.emissiveIntensity = lerp(a.room, b.room, t); MAT.roomDim.emissiveIntensity = lerp(a.roomDim, b.roomDim, t);
    MAT.ctxWin.emissiveIntensity = lerp(0, 1.1, t); MAT.ctxWin2.emissiveIntensity = lerp(0, 0.12, t);
    MAT.lamp.emissiveIntensity = lerp(a.lamp, b.lamp, t);
    MAT.glass.opacity = lerp(a.glass, b.glass, t);
    glowMat.opacity = lerp(a.street, b.street, t);
    trackMat.opacity = lerp(a.track, b.track, t);
    lerpC(_tmpSmoke, a.smoke, b.smoke, t);
  }
  const _tmpSmoke = new THREE.Color();

  /* ---------- camera rig ---------- */
  let lastRad = 0, freeCam = false;
  let cam = { at: V3(0,0,0), dist: 300, az: 22, el: 30, fx: 800, fy: 450 }, camFrom = null, camTo = null, camT = 0, drift = 0, driftAcc = 0;
  const CAM_DUR = 2.3;
  const ease = t => t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t+2, 3)/2;
  function normCam(c){ return { at: Array.isArray(c.at) ? V3(c.at[0], c.at[1], c.at[2]) : c.at.clone(), dist: c.dist, az: c.az, el: c.el, fx: c.fx ?? 800, fy: c.fy ?? 450 }; }
  function setCamera(c, instant){
    const t = normCam(c);
    const curAz = cam.az + driftAcc;
    if(instant){ cam = t; camTo = null; }
    else { camFrom = { at: cam.at.clone(), dist: cam.dist, az: curAz, el: cam.el, fx: cam.fx, fy: cam.fy }; cam = { ...camFrom, at: camFrom.at.clone() }; camTo = t; camT = 0; }
    drift = c.drift || 0; driftAcc = 0;
  }
  function applyCamera(){
    const az = (cam.az + driftAcc)*DEG, el = cam.el*DEG;
    camera.position.set(cam.at.x + cam.dist*Math.sin(az)*Math.cos(el), cam.at.y + cam.dist*Math.sin(el), cam.at.z + cam.dist*Math.cos(az)*Math.cos(el));
    camera.lookAt(cam.at);
    camera.setViewOffset(W, H, 800 - cam.fx, 450 - cam.fy, W, H);
    camera.updateMatrixWorld();
    const half = Math.max(45, Math.min(300, cam.dist*0.85));
    const sc = sun.shadow.camera;
    if(Math.abs(sc.right - half) > 0.5 || sun.target.position.distanceToSquared(cam.at) > 0.25 || shadowDirty){
      sc.left = -half; sc.right = half; sc.top = half; sc.bottom = -half; sc.updateProjectionMatrix();
      _sd.copy(SUN_DIR).add(sunOff).normalize();
      sun.target.position.copy(cam.at); sun.position.copy(cam.at).addScaledVector(_sd, 600);
      sun.target.updateMatrixWorld(); sun.updateMatrixWorld();
      renderer.shadowMap.needsUpdate = true; shadowDirty = false;
    }
    if(gtao){ const rad = Math.max(1.6, Math.min(12, cam.dist*0.05)); if(Math.abs(rad - lastRad) > 0.01){ gtao.updateGtaoMaterial({ radius: rad }); lastRad = rad; } }
  }

  /* ---------- per-frame ---------- */
  const _v = new THREE.Vector3();
  function update(dt, opts2){
    const rm = opts2 && opts2.reducedMotion;
    if(camTo){
      camT += dt/CAM_DUR; const e = ease(Math.min(1, camT));
      cam.at.lerpVectors(camFrom.at, camTo.at, e);
      cam.dist = Math.exp(lerp(Math.log(camFrom.dist), Math.log(camTo.dist), e));
      cam.az = lerp(camFrom.az, camTo.az, e); cam.el = lerp(camFrom.el, camTo.el, e);
      cam.fx = lerp(camFrom.fx, camTo.fx, e); cam.fy = lerp(camFrom.fy, camTo.fy, e);
      if(camT >= 1){ cam = { ...camTo, at: camTo.at.clone() }; camTo = null; }
    }
    if(!rm) driftAcc += drift*dt;
    if(!freeCam) applyCamera();
    mood += (moodTarget - mood) * Math.min(1, dt*1.6); applyMood();
    const dScale = 60/cam.dist;
    for(const id in F){
      const f = F[id];
      f.o += (f.target - f.o) * Math.min(1, dt*3.2);
      const vis = f.o > 0.004;
      f.glow.visible = f.base.visible = f.dash.visible = vis; f.dots[0].visible = f.dots[1].visible = vis;
      if(!vis) continue;
      f.glow.material.opacity = 0.18*f.o; f.base.material.opacity = 0.85*f.o; f.dash.material.opacity = f.o; f.dotMat.opacity = f.o;
      const lw = KIND_W[f.kind] || 3;
      f.base.material.linewidth = lw; f.dash.material.linewidth = lw*0.7; f.glow.material.linewidth = lw*3.2;
      f.dash.material.dashScale = dScale;
      if(!rm) f.off += (KIND_V[f.kind] || 1.3) * f.speed * dt;
      f.dash.material.dashOffset = -f.off;
      const r = 0.0028*cam.dist*(lw/3.4);
      f.dots.forEach(d => d.scale.setScalar(r));
    }
    smokeLevel += (smokeTarget - smokeLevel) * Math.min(1, dt*0.8);
    const ts = performance.now()/1000;
    puffs.forEach(p => {
      const life = rm ? (p.ph % 6)/6 : ((ts + p.ph) % 6)/6;
      p.s.position.set(p.src.x + life*30, p.src.y + life*26, p.src.z - life*4);
      const sc = 10 + life*30; p.s.scale.set(sc, sc, 1);
      p.s.material.opacity = (1-life) * Math.min(1, life*6) * 0.9 * smokeLevel;
      p.s.material.color.copy(_tmpSmoke);
    });
  }
  function render(){
    lineMats.forEach(m => m.resolution.set(W, H));
    if(composer) composer.render(); else renderer.render(scene, camera);
  }
  function project(v){ _v.copy(v).project(camera); return [(_v.x+1)/2*W, (1-_v.y)/2*H, _v.z]; }

  /* ---------- exports ---------- */
  function download(blob, name){ const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500); }
  function saveStill(name, scale){
    const old = pr; setPixelRatio(scale || 2.4); render();
    canvas.toBlob(b => download(b, (name || 'commonwatt') + '.png'), 'image/png');
    setPixelRatio(old);
  }
  function exportGLB(name){
    const ex = new X.GLTFExporter();
    ex.parse(world, glb => download(new Blob([glb], { type:'model/gltf-binary' }), (name || 'commonwatt-neighborhood') + '.glb'), err => console.error(err), { binary: true });
  }

  return {
    THREE, scene, camera, renderer, world, fx, B, F, MAT, PAL,
    smokeSources, place, finishLeaves, addFlow, setFlow, allFlowsOff, addWire, catenary, groundGlow, addSmoke,
    setSmoke(l){ smokeTarget = l; }, setMood(m){ moodTarget = (m === 'evening' || m === 1) ? 1 : 0; }, snapMood(){ mood = moodTarget; applyMood(); },
    composer, gtao, markShadows(){ shadowDirty = true; },
    setFreeCam(on){ freeCam = !!on; if(!on) shadowDirty = true; }, isFreeCam: () => freeCam,
    setSunOffset(dx, dz){ sunOff.set(dx || 0, 0, dz || 0); shadowDirty = true; applyCamera(); },
    setCamera, update, render, project, setPixelRatio, getPixelRatio: () => pr, saveStill, exportGLB,
    anchor(b, name){ const bd = B[b]; if(!bd) return null; if(Array.isArray(name)) return bd.toW ? bd.toW(name) : V3(bd.x+name[0], name[1], bd.z+name[2]); return bd.anchors[name] ? bd.anchors[name].clone() : null; },
    get cam(){ return cam; }
  };
}

/* =====================================================================
   NEIGHBORHOOD: the MassWatt demo blocks in Cambridge, MA.
   Laid out like a real distribution grid: the substation feeds an
   underground primary feeder along the commercial street (Main St);
   a residential side street (Elm St) gets an overhead lateral on wood
   poles with a pole-top transformer and service drops to each house;
   a second lateral runs underground up Oak St to the civic site on
   Broadway, where the library has its own service.
   ===================================================================== */
const STREET = {
  main:  { z: 0,   half: 4.5 },     // Main St (commercial corridor), runs east-west
  broad: { z: -82, half: 5 },       // Broadway, parallel to Main
  elm:   { x: -30, half: 4 },       // Elm St (residential), runs north-south
  oak:   { x: 39.5, half: 4.5 },    // Oak St, runs north-south
  feederZ: -7.2,                    // underground primary along Main St's north sidewalk
  busZ: -7.2
};

/* white-model window: a recessed-looking panel with sill and head */
function ctxWin(bb, F, u0, u1, v0, v1){
  const cu = (u0+u1)/2, du = u1-u0;
  fbox(bb, F, bb.r() < 0.55 ? 'ctxWin' : 'ctxWin2', cu, v0, 0.012, du, v1-v0, 0.025);
  fbox(bb, F, 'ctx', cu, v0-0.09, 0.07, du+0.24, 0.09, 0.16);
  fbox(bb, F, 'ctx', cu, v1, 0.05, du+0.14, 0.12, 0.1);
}
function ctxGable(bb, W, D, H, RH, ov){
  const sh = new THREE.Shape(); sh.moveTo(-W/2, 0); sh.lineTo(W/2, 0); sh.lineTo(0, RH); sh.closePath();
  const pg = new THREE.ExtrudeGeometry(sh, { depth: D, bevelEnabled: false }); pg.translate(0, 0, -D/2);
  bb.add('ctx', pg, 0, H, 0);
  const th = Math.atan2(RH, W/2), L = Math.hypot(RH, W/2) + ov, T = 0.16;
  for(const s of [-1, 1]){
    const ex = s*(W/2 + ov*Math.cos(th)), ey = H - ov*Math.sin(th);
    bb.boxC('ctxRoof', ex/2 + s*Math.sin(th)*T/2, (ey+H+RH)/2 + Math.cos(th)*T/2, 0, L, T, D+0.6, 0, 0, -s*th);
  }
}

/* White-model context house: Cambridge triple-decker (flat roof, stacked porches) or gable two-family. Faces +z. */
BUILD.ctxHouse = function(bb, o){
  o = o || {}; const R = bb.r;
  const fl = o.floors || (R() < 0.55 ? 3 : 2), gable = o.gable ?? (fl === 2 || R() < 0.3);
  const W = o.w || (7.6 + R()*1.6), D = o.d || (10.5 + R()*2.5), FH = 3.0, H = 0.6 + fl*FH;
  bb.box('ctx', 0, 0, 0, W+0.3, 0.6, D+0.3);
  bb.box('ctx', 0, 0.6, 0, W, H-0.6, D);
  const FS = FACE('z', D/2), FE = FACE('x', W/2), FW = FACE('x', -W/2, -1);
  const px = W/2 - 1.7;
  for(let f=0; f<fl; f++){
    const y0 = 0.6 + f*FH + 0.75, y1 = y0 + 1.6;
    ctxWin(bb, FS, -W/2+0.8, -W/2+1.6, y0, y1); ctxWin(bb, FS, -W/2+1.95, -W/2+2.75, y0, y1);
    ctxWin(bb, FS, px-0.45, px+0.45, y0, y1);
    for(let k=0;k<3;k++){ const z = -D/2 + 1.6 + k*(D-3.2)/2; ctxWin(bb, FE, z-0.45, z+0.45, y0, y1); ctxWin(bb, FW, z-0.45, z+0.45, y0, y1); }
    bb.box('ctx', 0, 0.6 + (f+1)*FH - 0.12, D/2+0.02, W+0.04, 0.12, 0.06);
  }
  // stacked porches on the door side
  for(let f=0; f<fl; f++){
    const y = 0.6 + f*FH;
    bb.box('ctx', px, y-0.18, D/2+1.05, 3.1, 0.18, 2.1);
    for(const dx of [-1.4, 1.4]) bb.box('ctx', px+dx, y, D/2+1.95, 0.16, FH-0.18, 0.16);
    bb.box('ctx', px, y+0.95, D/2+1.97, 2.8, 0.07, 0.07);
    for(let u=-1.2; u<=1.21; u+=0.3) bb.box('ctx', px+u, y, D/2+1.97, 0.04, 0.95, 0.04);
  }
  bb.box('ctx', px, 0.6+fl*FH-0.18, D/2+1.05, 3.3, 0.2, 2.3);
  fbox(bb, FS, 'ctxWin2', px, 0.6, 0.015, 0.95, 2.1, 0.03);
  bb.box('ctx', px, 0, D/2+2.4, 1.3, 0.3, 0.7); bb.box('ctx', px, 0, D/2+2.8, 1.3, 0.15, 0.5);
  if(gable) ctxGable(bb, W, D, H, 3.2 + R()*0.8, 0.4);
  else { bb.box('ctx', 0, H, 0, W+0.5, 0.32, D+0.5); bb.box('ctxRoof', 0, H+0.32, 0, W+0.3, 0.02, D+0.3); for(let u=-W/2+0.4; u<W/2; u+=0.9) bb.box('ctx', u, H-0.3, D/2+0.2, 0.14, 0.3, 0.14); }
  return { anchors:{ top:[0, H+6, 0] } };
};

/* White-model commercial block: storefronts, sign band, upper windows, cornice. Faces +z. */
BUILD.ctxShop = function(bb, o){
  o = o || {}; const R = bb.r;
  const W = o.w || 14, D = o.d || 12, fl = o.floors || (2 + Math.floor(R()*2)), G = 4.2, FH = 3.3, H = G + (fl-1)*FH;
  bb.box('ctx', 0, 0, 0, W, H, D);
  const FS = FACE('z', D/2), FE = FACE('x', W/2);
  const bays = Math.max(2, Math.round(W/3.4)), bw = (W-0.8)/bays;
  for(let i=0;i<bays;i++){
    const u0 = -W/2+0.4 + i*bw + 0.15, u1 = u0 + bw - 0.3;
    fbox(bb, FS, 'ctxWin', (u0+u1)/2, 0.45, 0.015, u1-u0, 2.75, 0.03);
    fbox(bb, FS, 'ctx', (u0+u1)/2, 2.55, 0.05, u1-u0, 0.07, 0.08);
    fbox(bb, FS, 'ctx', u0-0.1, 0.0, 0.08, 0.22, 3.4, 0.16);
    for(let f=1; f<fl; f++) for(const k of [0.28, 0.72]){ const u = u0 + (u1-u0)*k; ctxWin(bb, FS, u-0.42, u+0.42, G + (f-1)*FH + 0.75, G + (f-1)*FH + 2.35); }
  }
  fbox(bb, FS, 'ctx', W/2-0.3, 0.0, 0.08, 0.22, 3.4, 0.16);
  fbox(bb, FS, 'ctx', 0, 3.3, 0.12, W+0.1, 0.65, 0.24);
  for(let f=1; f<fl; f++) for(let k=0;k<3;k++){ const z = -D/2 + 2 + k*(D-4)/2; ctxWin(bb, FE, z-0.5, z+0.5, G + (f-1)*FH + 0.75, G + (f-1)*FH + 2.35); }
  if(R() < 0.5) for(let i=0;i<bays;i++){ const u = -W/2+0.4 + (i+0.5)*bw; bb.boxC('ctx', u, 3.1, D/2+0.75, bw-0.5, 0.05, 1.5, 0.35); }
  bb.box('ctx', 0, H, 0, W+0.5, 0.4, D+0.5); bb.box('ctx', 0, H+0.4, 0, W+0.1, 0.5, D+0.1); bb.box('ctxRoof', 0, H+0.9, 0, W-0.3, 0.02, D-0.3);
  return { anchors:{ top:[0, H+6, 0] } };
};

/* Wood utility pole: crossarm with three primary conductors, secondary rack, optional pole-top transformer. Street runs along z. */
BUILD.pole = function(bb, o){
  o = o || {}; const H = 11;
  bb.cyl('wood2', 0, 0, 0, 0.17, H, 10, 0.12);
  bb.box('wood2', 0, H-0.95, 0, 2.6, 0.14, 0.14);
  for(const x of [-1.1, 0, 1.1]){ bb.cyl('clay2', x, H-0.81, 0, 0.07, 0.28, 10); bb.cyl('clay2', x, H-0.6, 0, 0.11, 0.05, 12); }
  bb.box('metalDark', 0.2, H-4.7, 0, 0.12, 0.6, 0.12);
  if(o.transformer){ bb.cyl('metal', 0.5, H-3.6, 0, 0.36, 1.2, 18); bb.cyl('metal', 0.5, H-2.4, 0, 0.38, 0.06, 18); bb.cyl('clay2', 0.5, H-2.35, 0, 0.06, 0.35, 8); bb.seg('metalDark', [0.5, H-2.0, 0], [0, H-0.7, 0], 0.03); }
  return { anchors:{ top:[0, H+2, 0] } };
};

function buildNeighborhood(stage){
  const T = THREE, S = STREET;
  const ground = new T.Mesh(new T.PlaneGeometry(4000, 4000).rotateX(-Math.PI/2), MAT.ground); ground.receiveShadow = true; ground.name = 'ground'; stage.world.add(ground);

  /* ---------- streets, sidewalks, crosswalks, lamps ---------- */
  stage.place('streets', 0, 0, bb => {
    const X0 = -170, X1 = 240, Z1 = -150;
    const ns = (x, half, zA, zB) => {   // a north-south street from zA (south) to zB (north)
      bb.box('asphalt', x, 0, (zA+zB)/2, half*2, 0.02, zA-zB);
      for(const s of [-1, 1]) bb.box('sidewalk', x + s*(half+1.5), 0, (zA+zB)/2, 3, 0.15, zA-zB);
      for(let z=zA-4; z>zB+2; z-=8) bb.box('paint', x, 0.02, z, 0.16, 0.012, 3.2);
    };
    const ew = (z, half, xA, xB, gaps) => {
      bb.box('asphalt', (xA+xB)/2, 0, z, xB-xA, 0.02, half*2);
      for(const s of [-1, 1]){
        let a = xA;
        for(const g of gaps.concat([[xB, xB]])){ if(g[0] > a) bb.box('sidewalk', (a+g[0])/2, 0, z + s*(half+1.5), g[0]-a, 0.15, 3); a = g[1]; }
      }
      for(let x=xA+2; x<xB-2; x+=8){ if(gaps.some(g => x > g[0]-2 && x < g[1]+2)) continue; bb.box('paint', x, 0.02, z, 3.2, 0.012, 0.16); }
    };
    const cross = (x, z, alongX) => { for(let k=-3;k<=3;k++) alongX ? bb.box('paint', x + k*1.0, 0.02, z, 0.5, 0.012, 2.6) : bb.box('paint', x, 0.02, z + k*1.0, 2.6, 0.012, 0.5); };
    const elmGap = [S.elm.x - S.elm.half - 3, S.elm.x + S.elm.half + 3], oakGap = [S.oak.x - S.oak.half - 3, S.oak.x + S.oak.half + 3];
    ew(S.main.z, S.main.half, X0, X1, []);
    ew(S.broad.z, S.broad.half, X0, 95, [elmGap, oakGap]);
    const zMainN = S.main.z - S.main.half - 3, zBroadS = S.broad.z + S.broad.half + 3, zBroadN = S.broad.z - S.broad.half - 3;
    for(const st of [S.elm, S.oak]){
      ns(st.x, st.half, zMainN, zBroadS); ns(st.x, st.half, zBroadN, Z1);
      bb.box('asphalt', st.x, 0, S.broad.z, st.half*2, 0.02, zBroadS - zBroadN);
      cross(st.x, zMainN - 1.8, true); cross(st.x, zBroadS - 1.8, true); cross(st.x, zBroadN + 1.8, true);
    }
    cross(S.elm.x - S.elm.half - 1.8, S.main.z, false); cross(S.oak.x + S.oak.half + 1.8, S.main.z, false);
    bb.box('grass', 30, 0, 12, 420, 0.04, 9);
    const lamp = (x, z, dx, dz) => { bb.cyl('metalDark', x, 0.15, z, 0.08, 6.4, 8); bb.box('metalDark', x+dx*0.65, 6.45, z+dz*0.65, Math.abs(dx)*1.3+0.08, 0.08, Math.abs(dz)*1.3+0.08); bb.box('lamp', x+dx*1.25, 6.3, z+dz*1.25, 0.32+Math.abs(dx)*0.28, 0.12, 0.32+Math.abs(dz)*0.28); stage.groundGlow(x+dx*2.2, z+dz*2.2, 9); };
    for(let x=-160; x<236; x+=26){ if([S.elm.x, S.oak.x].some(sx => Math.abs(x-sx) < 9)) continue; lamp(x, -4.95, 0, 1); lamp(x+13, 4.95, 0, -1); }
    for(let x=-150; x<92; x+=28){ if([S.elm.x, S.oak.x].some(sx => Math.abs(x-sx) < 9)) continue; lamp(x, S.broad.z + S.broad.half + 0.45, 0, -1); }
    for(let z=-20; z>-140; z-=28){ if(Math.abs(z - S.broad.z) < 9) continue; lamp(S.oak.x + S.oak.half + 0.45, z, -1, 0); }
    for(const x of [-60, 60]) bb.box('wood', x, 0.15, 6.6, 2.6, 0.45, 0.6);
    figure(bb, -14, 0.15, 6.2, -1.57, 'walk'); figure(bb, 16, 0.15, 5.6, 1.57, 'walk'); figure(bb, 70, 0.15, -6.4, -1.57, 'walk');
    figure(bb, S.elm.x + 5.6, 0.15, -40, 0, 'walk'); figure(bb, S.oak.x + 6, 0.15, -60, Math.PI, 'walk');
  });

  /* ---------- members ---------- */
  const E = Math.PI/2;
  stage.place('office', -70, -20, BUILD.office);
  stage.place('cafe', -14, -14.5, BUILD.cafe);                                      // corner of Main St and Elm St
  stage.place('home03', -45, -44, BUILD.gableHouse, { hp:true, ev:true, evFlow:'h3_ev_home' }, 11, E);   // Elm St, west side, faces east
  stage.place('home05', -45, -62, BUILD.gableHouse, { pv:true, battery:true, batFlow:'h5_bat_home' }, 23, E);
  stage.place('home07', -15.5, -52, BUILD.modernHome, null, 0, -E);                // Elm St, east side, faces west
  stage.place('library', 62, -102, BUILD.library);                                   // Broadway, civic site
  stage.place('substation', 100, -16, BUILD.substation);

  /* ---------- white-model context, block by block ---------- */
  let ci = 0;
  const ctx = (fn, x, z, ry, o) => stage.place('ctx' + (ci++), x, z, fn, o, 101 + ci*7, ry);
  // Main St frontage (north side): storefront blocks
  ctx(BUILD.ctxShop, -42.5, -14.2, 0, { w: 9, d: 12, floors: 2 });
  for(const [x, w] of [[6, 13], [22.5, 14], [56, 14], [73, 13]]) ctx(BUILD.ctxShop, x, -14.5, 0, { w, d: 12.5 });
  // Elm St houses
  ctx(BUILD.ctxHouse, -17.5, -68, -E, { floors: 3 });
  for(const z of [-100, -116, -132]){ ctx(BUILD.ctxHouse, -43.5, z, E); ctx(BUILD.ctxHouse, -16.5, z, -E); }
  // Oak St houses
  for(const z of [-30, -46, -62]){ ctx(BUILD.ctxHouse, 26, z, E); ctx(BUILD.ctxHouse, 53.5, z, -E); }
  // Broadway: houses facing the street on both sides
  for(const x of [-78, -62]) ctx(BUILD.ctxHouse, x, -67.5, Math.PI);
  for(const x of [-2, 12]) ctx(BUILD.ctxHouse, x, -67.5, Math.PI);
  for(const x of [-76, -60, -12, 4, 20]) ctx(BUILD.ctxHouse, x, -97, 0);
  for(const x of [-100, -116]) for(const z of [-30, -50]) ctx(BUILD.ctxHouse, x, z, E);
  ctx(BUILD.ctxShop, 76, -68.5, Math.PI, { w: 13, d: 12, floors: 2 });

  /* ---------- utility poles on Elm St (overhead lateral) ---------- */
  const PX = S.elm.x - S.elm.half - 0.6, poleZ = [-9.5, -31, -52, -73];
  const poles = poleZ.map((z, i) => { stage.place('pole' + i, PX, z, BUILD.pole, { transformer: z === -52 }); return z; });
  const H = 11, prim = (z, k) => V3(PX + (k-1)*1.1, H-0.5, z), secY = H - 4.4;
  for(let i=0;i<poles.length-1;i++){
    for(let k=0;k<3;k++) stage.addWire(stage.catenary(prim(poles[i], k), prim(poles[i+1], k), 0.7));
    stage.addWire(stage.catenary(V3(PX+0.2, secY, poles[i]), V3(PX+0.2, secY, poles[i+1]), 0.5));
  }
  const xfmr = V3(PX+0.5, H-3.0, -52);

  /* ---------- transmission line, plant ---------- */
  const sub = V3(100, 0, -16), plantAt = V3(178, 0, -108);
  const dir = plantAt.clone().sub(sub); dir.y = 0; const L = dir.length(); dir.normalize();
  const ry = Math.atan2(dir.x, dir.z);
  const towers = [];
  [0.24, 0.48, 0.72].forEach((f, i) => {
    const p = sub.clone().addScaledVector(dir, L*f); let att = null;
    const b = stage.place('tower'+i, p.x, p.z, bb => { att = BUILD.tower(bb, 34); return {}; }, null, 0, ry);
    towers.push(att.map(a => b.toW(a)));
  });
  let tops = [];
  const plant = stage.place('plant', plantAt.x, plantAt.z, bb => { tops = BUILD.plant(bb); return { anchors:{ top:[0, 70, 0] } }; }, null, 0, ry + Math.PI);
  tops.forEach(t => stage.addSmoke(plant.toW(t)));
  const gantry = stage.B.substation.anchors.gantry;
  const plantPort = plant.toW([0, 16, 30]);
  for(let k=0;k<4;k++){
    const chain = [V3(gantry.x + (k-1.5)*2.6, gantry.y - 1.4, gantry.z), ...towers.map(t => t[k]), plantPort.clone().add(V3((k-1.5)*3, 0, 0))];
    for(let i=0;i<chain.length-1;i++) stage.addWire(stage.catenary(chain[i], chain[i+1], i === 0 || i === chain.length-2 ? 1.2 : 3.2));
  }
  stage.finishLeaves();

  /* ---------- energy lines along the real network ---------- */
  const tr = [plantPort, ...towers.slice().reverse().map(t => t[3]), V3(gantry.x+2.6, gantry.y-1.4, gantry.z)];
  const trunk = [];
  for(let i=0;i<tr.length-1;i++){ const seg = stage.catenary(tr[i], tr[i+1], i === 0 || i === tr.length-2 ? 1.2 : 3.2, 10); if(i) seg.shift(); trunk.push(...seg); }
  trunk.push(V3(sub.x+2.6, 3.2, sub.z-3.2), V3(sub.x+2.6, 0.3, sub.z+3.0), V3(sub.x+2.6, 0.3, S.feederZ));
  stage.addFlow('trunk', trunk);
  const B = stage.B;
  // primary feeder under Main St, substation to the office
  stage.addFlow('bus', [V3(sub.x+2.6, 0.3, S.feederZ), V3(B.office.svc.x, 0.3, S.feederZ)]);
  // overhead lateral up Elm St: riser on the corner pole, then along the middle conductor
  const elm = [V3(PX, 0.3, S.feederZ), V3(PX, 0.3, poles[0]), prim(poles[0], 1)];
  for(let i=0;i<poles.length-1;i++){ const seg = stage.catenary(prim(poles[i], 1), prim(poles[i+1], 1), 0.7, 8); seg.shift(); elm.push(...seg); }
  stage.addFlow('bus_elm', elm.filter((p, i) => i < 3 || p.z >= -52.01));
  // underground lateral up Oak St to the library on Broadway
  const OX = S.oak.x + S.oak.half + 1.5, BZ = S.broad.z - S.broad.half - 1.5;
  stage.addFlow('bus_oak', [V3(OX, 0.3, S.feederZ), V3(OX, 0.3, BZ), V3(B.library.svc.x, 0.3, BZ)]);
  // service connections
  const drop = (k, pts) => { stage.addFlow(k+'_in', pts, { noTrack: true }); stage.addFlow(k+'_out', pts.slice().reverse()); B[k].busPoint = pts[0].clone(); };
  drop('office', [V3(B.office.svc.x, 0.3, S.feederZ), V3(B.office.svc.x, 0.3, B.office.svc.z)]);
  drop('cafe', [V3(B.cafe.svc.x, 0.3, S.feederZ), V3(B.cafe.svc.x, 0.3, B.cafe.svc.z)]);
  drop('library', [V3(B.library.svc.x, 0.3, BZ), V3(B.library.svc.x, 0.3, B.library.svc.z)]);
  // overhead service drops from the pole-top transformer to each house
  for(const k of ['home03', 'home05', 'home07']){
    const b = B[k], m = b.svc, attach = V3(m.x, k === 'home07' ? 3.1 : 5.4, m.z);
    const wire = stage.catenary(V3(PX+0.2, secY, -52), attach, 0.6, 10);
    stage.addWire(wire, '#7d838a');
    drop(k, [xfmr.clone(), ...wire, V3(m.x, 0.3, m.z)]);
  }
  stage.B.grid = { key:'grid', anchors:{ top: towers[0][0].clone().setY(52), bus: V3(sub.x, 0.3, S.feederZ) } };
  return stage.B;
}

return { options: OPT, THREE, PAL, MAT, MOOD, Builder, BUILD, FACE, win, figure, sofa, table, roundTable, chair, potPlant, bookshelf, pvArray, heatPump, homeBattery, ev, evCharger, rooftopUnit, fence, createStage, buildNeighborhood, STREET };
};
})();
