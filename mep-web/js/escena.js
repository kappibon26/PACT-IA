// Vista 3D y planta con three.js. El modelo está en mm; la escena en metros (S = 0.001), Z arriba.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { FAMILIAS } from './catalogo.js';
import { colorSistema, conectoresEquipo, ejesTramo, familia, longitud, rotulo, seccion } from './modelo.js';

const S = 0.001;
const v3 = (p) => new THREE.Vector3(p[0] * S, p[1] * S, p[2] * S);

export class Escena {
  constructor(contenedor) {
    this.el = contenedor;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.localClippingEnabled = true;
    contenedor.appendChild(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8f94, 1.6));
    const sol = new THREE.DirectionalLight(0xffffff, 1.5);
    sol.position.set(-30, -50, 80);
    this.scene.add(sol);

    this.persp = new THREE.PerspectiveCamera(42, 1, 0.05, 2000);
    this.persp.up.set(0, 0, 1);
    this.persp.position.set(-14, -30, 22);
    this.orto = new THREE.OrthographicCamera(-20, 20, 20, -20, 0.1, 2000);
    this.orto.up.set(0, 1, 0);

    this.ctrl3d = new OrbitControls(this.persp, this.renderer.domElement);
    this.ctrl3d.target.set(6, 0, 2);
    this.ctrl3d.enableDamping = true;
    this.ctrlPlanta = new OrbitControls(this.orto, this.renderer.domElement);
    this.ctrlPlanta.enableRotate = false;
    this.ctrlPlanta.mouseButtons = { LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
    this.ctrlPlanta.touches = { ONE: THREE.TOUCH.PAN, TWO: THREE.TOUCH.DOLLY_PAN };
    this.ctrlPlanta.screenSpacePanning = true;
    this.ctrlPlanta.enabled = false;

    this.grupos = {};
    for (const k of ['equipos', 'tramos', 'accesorios', 'marcas', 'guia', 'etiquetas', 'conectores']) {
      this.grupos[k] = new THREE.Group();
      this.scene.add(this.grupos[k]);
    }
    this.mats = new Map();
    this.cacheFamilia = new Map();
    this.cortes = [new THREE.Plane(new THREE.Vector3(0, 0, -1), 1e6), new THREE.Plane(new THREE.Vector3(0, 0, 1), 1e6)];
    this.vista = '3d';
    this.raycaster = new THREE.Raycaster();
    this.tema = { fondo: '#e9ebe8', grilla: '#c6cbc6', grillaFuerte: '#a9b0aa', acento: '#e0620f' };

    this.cursor = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 12), new THREE.MeshBasicMaterial({ color: 0xe0620f, depthTest: false }));
    this.cursor.renderOrder = 10;
    this.cursor.visible = false;
    this.grupos.guia.add(this.cursor);
    this.preview = new THREE.Group();
    this.grupos.guia.add(this.preview);

    new ResizeObserver(() => this.ajustar()).observe(contenedor);
    this.ajustar();
    const loop = () => {
      (this.vista === '3d' ? this.ctrl3d : this.ctrlPlanta).update();
      this.escalarEtiquetas();
      this.renderer.render(this.scene, this.camara);
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  get camara() { return this.vista === '3d' ? this.persp : this.orto; }

  ajustar() {
    const w = this.el.clientWidth || 1, h = this.el.clientHeight || 1;
    this.renderer.setSize(w, h, false);
    this.persp.aspect = w / h;
    this.persp.updateProjectionMatrix();
    const a = w / h, alto = 20;
    Object.assign(this.orto, { left: -alto * a, right: alto * a, top: alto, bottom: -alto });
    this.orto.updateProjectionMatrix();
  }

  setTema(t) {
    Object.assign(this.tema, t);
    this.scene.background = new THREE.Color(this.tema.fondo);
    this.cursor.material.color.set(this.tema.acento);
    if (this._grilla) this.grilla(this._grilla.z, this._grilla.paso);
  }

  // -------------------------------------------------------------- vistas
  setVista(v, nivel, techo) {
    this.vista = v;
    this.ctrl3d.enabled = v === '3d';
    this.ctrlPlanta.enabled = v === 'planta';
    if (v === 'planta') {
      const t = this.ctrl3d.target;
      this.orto.position.set(t.x, t.y, 500);
      this.ctrlPlanta.target.set(t.x, t.y, 0);
      this.orto.lookAt(t.x, t.y, 0);
      // rango de vista: del piso del nivel al siguiente nivel
      this.cortes[0].constant = (techo - 1) * S;
      this.cortes[1].constant = -(nivel - 1) * S;
    } else {
      this.cortes[0].constant = 1e6;
      this.cortes[1].constant = 1e6;
    }
    this.renderer.clippingPlanes = v === 'planta' ? this.cortes : [];
  }

  encuadrar(min, max) {
    const c = v3([(min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2]);
    const r = Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2]) * S * 0.75 + 1;
    this.ctrl3d.target.copy(c);
    this.persp.position.copy(c).add(new THREE.Vector3(-0.55, -1.25, 0.85).multiplyScalar(r * 1.0));
    this.ctrlPlanta.target.set(c.x, c.y, 0);
    this.orto.position.set(c.x, c.y, 500);
    const a = this.persp.aspect;
    this.orto.zoom = Math.min(20 / ((max[1] - min[1]) * S * 0.6 + 1), (20 * a) / ((max[0] - min[0]) * S * 0.6 + 1));
    this.orto.updateProjectionMatrix();
  }

  // -------------------------------------------------------------- materiales
  mat(color, opts = {}) {
    const k = color + JSON.stringify(opts);
    if (!this.mats.has(k)) {
      this.mats.set(k, new THREE.MeshStandardMaterial({ color, roughness: 0.62, metalness: 0.08, side: THREE.DoubleSide, ...opts }));
    }
    return this.mats.get(k);
  }
  matLinea(color) {
    const k = 'L' + color;
    if (!this.mats.has(k)) this.mats.set(k, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.55 }));
    return this.mats.get(k);
  }

  // -------------------------------------------------------------- grilla del plano de trabajo
  grilla(z, paso = 1000) {
    this._grilla = { z, paso };
    const g = this.grupos.guia;
    if (this._lineas) { g.remove(this._lineas); this._lineas.children.forEach((c) => { c.geometry.dispose(); c.material.dispose(); }); }
    const pts = [], fuertes = [];
    const R = 60000;
    for (let x = -R; x <= R; x += paso) {
      const arr = Math.round(x / paso) % 5 === 0 ? fuertes : pts;
      arr.push(x * S, -R * S, z * S, x * S, R * S, z * S, -R * S, x * S, z * S, R * S, x * S, z * S);
    }
    const geo = (a) => { const b = new THREE.BufferGeometry(); b.setAttribute('position', new THREE.Float32BufferAttribute(a, 3)); return b; };
    this._lineas = new THREE.Group();
    this._lineas.add(new THREE.LineSegments(geo(pts), new THREE.LineBasicMaterial({ color: this.tema.grilla, transparent: true, opacity: 0.5 })));
    this._lineas.add(new THREE.LineSegments(geo(fuertes), new THREE.LineBasicMaterial({ color: this.tema.grillaFuerte, transparent: true, opacity: 0.7 })));
    g.add(this._lineas);
  }

  // -------------------------------------------------------------- geometría
  geoTramo(t, extra = 0) {
    const sc = seccion(t);
    const L = longitud(t) * S;
    const { d, s, u } = ejesTramo(t.a, t.b);
    const m = new THREE.Matrix4().makeBasis(v3(s).normalize(), v3(u).normalize(), v3(d).normalize());
    m.setPosition(v3([(t.a[0] + t.b[0]) / 2, (t.a[1] + t.b[1]) / 2, (t.a[2] + t.b[2]) / 2]));
    const w = (sc.w + extra) * S, h = (sc.h + extra) * S;
    let geos;
    if (sc.redondo) {
      const g = new THREE.CylinderGeometry(w / 2, w / 2, L, 20, 1, false);
      g.rotateX(Math.PI / 2);
      geos = [g];
    } else if (t.tipo === 'bandeja') {
      const e = 0.012;
      geos = [
        new THREE.BoxGeometry(w, e, L).translate(0, -h / 2 + e / 2, 0),
        new THREE.BoxGeometry(e, h, L).translate(-w / 2 + e / 2, 0, 0),
        new THREE.BoxGeometry(e, h, L).translate(w / 2 - e / 2, 0, 0),
      ];
    } else {
      geos = [new THREE.BoxGeometry(w, h, L)];
    }
    const g = geos.length > 1 ? mergeGeometries(geos) : geos[0];
    g.applyMatrix4(m);
    return g;
  }

  geoFamilia(id) {
    if (this.cacheFamilia.has(id)) return this.cacheFamilia.get(id);
    const f = FAMILIAS[id];
    const porColor = new Map();
    for (const [eje, a0, a1, col, poly] of f.prismas) {
      const sh = new THREE.Shape(poly.map(([u, v]) => new THREE.Vector2(u * S, v * S)));
      const g = new THREE.ExtrudeGeometry(sh, { depth: (a1 - a0) * S, bevelEnabled: false, curveSegments: 4 });
      // forma en (u, v) local XY y extrusión en Z local; se lleva al eje del prisma
      if (eje === 'Z') g.translate(0, 0, a0 * S);
      else if (eje === 'X') g.applyMatrix4(new THREE.Matrix4().set(0, 0, 1, a0 * S, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1));
      else g.applyMatrix4(new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, a0 * S, 0, 1, 0, 0, 0, 0, 0, 1));
      if (!porColor.has(col)) porColor.set(col, []);
      porColor.get(col).push(g.index ? g.toNonIndexed() : g);
    }
    const partes = [...porColor].map(([col, gs]) => {
      const g = mergeGeometries(gs);
      g.computeVertexNormals();
      return { col, g, bordes: new THREE.EdgesGeometry(g, 35) };
    });
    this.cacheFamilia.set(id, partes);
    return partes;
  }

  // -------------------------------------------------------------- dibujo del modelo
  dibujar(m, an, { sel = null, ocultos = new Set(), conectores = false, etiquetas = false, marcas = [] } = {}) {
    for (const k of ['tramos', 'accesorios', 'equipos', 'marcas', 'etiquetas', 'conectores']) {
      const g = this.grupos[k];
      for (const c of [...g.children]) {
        g.remove(c);
        c.traverse((o) => { if (o.geometry && !o.userData.compartida) o.geometry.dispose(); if (o.material && o.userData.propio) o.material.dispose(); });
      }
    }
    const selMat = this.mat(this.tema.acento, { emissive: this.tema.acento, emissiveIntensity: 0.35 });

    for (const t of an.tramos) {
      if (ocultos.has(t.sistema)) continue;
      const col = colorSistema(t.sistema);
      const g = this.geoTramo(t);
      const mesh = new THREE.Mesh(g, sel === t.id ? selMat : this.mat(col, t.tipo === 'ducto' ? { roughness: 0.45, metalness: 0.25 } : {}));
      mesh.userData = { id: t.id };
      if (!(seccion(t).redondo)) {
        const l = new THREE.LineSegments(new THREE.EdgesGeometry(g), this.matLinea('#1d2326'));
        mesh.add(l);
      }
      this.grupos.tramos.add(mesh);
      if (etiquetas && Math.hypot(t.b[0] - t.a[0], t.b[1] - t.a[1]) >= 1500) this.etiqueta(rotulo(t), t, col); // solo tramos horizontales largos
    }

    for (const a of an.accesorios) {
      if (ocultos.has(a.sistema)) continue;
      const sc = seccion(a.t);
      const col = new THREE.Color(colorSistema(a.sistema)).multiplyScalar(0.8).getStyle();
      const mat = this.mat(col);
      const lado = Math.max(sc.w, sc.h);
      let g;
      if (sc.redondo) g = new THREE.SphereGeometry((lado * 1.12 * S) / 2, 18, 12);
      else {
        g = new THREE.BoxGeometry(...(a.clase === 'bandeja' ? [sc.w * S, sc.h * S, sc.w * S] : [lado * 1.06 * S, lado * 1.06 * S, lado * 1.06 * S]));
        const { s, u, d } = ejesTramo([0, 0, 0], a.dirs[0]);
        g.applyMatrix4(new THREE.Matrix4().makeBasis(v3(s).normalize(), v3(u).normalize(), v3(d).normalize()));
        if (a.clase === 'bandeja') g.translate(...v3(a.dirs[0].map((x) => (-x * sc.w) / 2)).toArray());
      }
      g.translate(...v3(a.p).toArray());
      const mesh = new THREE.Mesh(g, mat);
      mesh.userData = { id: a.t.id, accesorio: a.id };
      this.grupos.accesorios.add(mesh);
    }

    for (const eq of m.elementos.filter((e) => e.tipo === 'equipo')) {
      const grp = new THREE.Group();
      grp.position.copy(v3(eq.pos));
      grp.rotation.z = ((eq.rot || 0) * Math.PI) / 180;
      for (const { col, g, bordes } of this.geoFamilia(eq.familia)) {
        const mesh = new THREE.Mesh(g, sel === eq.id ? selMat : this.mat(col));
        mesh.userData = { id: eq.id, compartida: true };
        const l = new THREE.LineSegments(bordes, this.matLinea('#20262a'));
        l.userData.compartida = true;
        mesh.add(l);
        grp.add(mesh);
      }
      grp.userData = { id: eq.id };
      this.grupos.equipos.add(grp);
      if (conectores || sel === eq.id) this.marcasConectores(eq);
    }

    for (const mk of marcas) {
      const mesh = new THREE.Mesh(new THREE.SphereGeometry(mk.r * S, 18, 12),
        new THREE.MeshBasicMaterial({ color: mk.color, transparent: true, opacity: 0.55, depthTest: false }));
      mesh.userData.propio = true;
      mesh.renderOrder = 5;
      mesh.position.copy(v3(mk.p));
      this.grupos.marcas.add(mesh);
    }
  }

  marcasConectores(eq) {
    for (const c of conectoresEquipo(eq)) {
      const col = c.tipo === 'electrico' ? '#e5b400' : colorSistema(c.sistema);
      const r = c.tipo === 'electrico' ? 45 : 60;
      const g = c.tipo === 'electrico' ? new THREE.OctahedronGeometry(r * S) : new THREE.ConeGeometry(r * S, r * 2.4 * S, 14);
      if (c.tipo !== 'electrico') {
        const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), v3(c.dir).normalize());
        g.applyQuaternion(q);
        g.translate(...v3(c.dir.map((x) => x * r * 1.2)).toArray());
      }
      const mesh = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color: col, depthTest: false }));
      mesh.userData.propio = true;
      mesh.renderOrder = 6;
      mesh.position.copy(v3(c.pos));
      this.grupos.conectores.add(mesh);
    }
  }

  etiqueta(txt, t, col) {
    const cv = document.createElement('canvas');
    const ctx = cv.getContext('2d');
    const fs = 44;
    ctx.font = `600 ${fs}px "IBM Plex Mono", monospace`;
    cv.width = Math.ceil(ctx.measureText(txt).width) + 24;
    cv.height = fs + 16;
    ctx.font = `600 ${fs}px "IBM Plex Mono", monospace`;
    ctx.fillStyle = 'rgba(255,255,255,0.92)';
    ctx.fillRect(0, 0, cv.width, cv.height);
    ctx.fillStyle = col;
    ctx.fillRect(0, cv.height - 6, cv.width, 6);
    ctx.fillStyle = '#1b2124';
    ctx.textBaseline = 'middle';
    ctx.fillText(txt, 12, cv.height / 2 - 2);
    const tex = new THREE.CanvasTexture(cv);
    tex.colorSpace = THREE.SRGBColorSpace;
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false }));
    sp.userData = { propio: true, px: [cv.width / 3.4, cv.height / 3.4] };
    sp.renderOrder = 8;
    sp.position.copy(v3([(t.a[0] + t.b[0]) / 2, (t.a[1] + t.b[1]) / 2, Math.max(t.a[2], t.b[2]) + 300]));
    this.grupos.etiquetas.add(sp);
  }

  // tamaño constante en pantalla: metros por píxel en la posición de cada etiqueta
  escalarEtiquetas() {
    const H = this.el.clientHeight || 1;
    for (const sp of this.grupos.etiquetas.children) {
      const k = this.vista === '3d'
        ? (this.persp.position.distanceTo(sp.position) * 2 * Math.tan((this.persp.fov * Math.PI) / 360)) / H
        : (this.orto.top - this.orto.bottom) / this.orto.zoom / H;
      sp.scale.set(sp.userData.px[0] * k, sp.userData.px[1] * k, 1);
    }
  }

  // -------------------------------------------------------------- vista previa del trazado
  limpiarPreview() {
    for (const c of [...this.preview.children]) { this.preview.remove(c); c.geometry && c.geometry.dispose(); }
  }
  mostrarPreview(tramos, color) {
    this.limpiarPreview();
    const mat = this.mat(color, { transparent: true, opacity: 0.5, depthWrite: false });
    for (const t of tramos) {
      if (longitud(t) < 1) continue;
      this.preview.add(new THREE.Mesh(this.geoTramo(t), mat));
    }
  }
  mostrarFantasma(famId, pos, rot) {
    this.limpiarPreview();
    const grp = new THREE.Group();
    grp.position.copy(v3(pos));
    grp.rotation.z = (rot * Math.PI) / 180;
    for (const { g } of this.geoFamilia(famId)) {
      const mesh = new THREE.Mesh(g.clone(), this.mat(this.tema.acento, { transparent: true, opacity: 0.35, depthWrite: false }));
      grp.add(mesh);
    }
    // fantasmas: el grupo no es un Mesh, se limpia por hijos
    grp.geometry = null;
    this.preview.add(grp);
  }
  ponerCursor(p, radio = 70) {
    if (!p) { this.cursor.visible = false; return; }
    this.cursor.visible = true;
    this.cursor.position.copy(v3(p));
    const escala = this.vista === '3d' ? this.persp.position.distanceTo(this.cursor.position) * 0.006 : 2.2 / this.orto.zoom * 0.12;
    this.cursor.scale.setScalar(Math.max(radio * S, escala));
  }

  // -------------------------------------------------------------- consultas de pantalla
  ndc(ev) {
    const r = this.renderer.domElement.getBoundingClientRect();
    return new THREE.Vector2(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
  }
  // punto (mm) donde el rayo del cursor corta el plano horizontal z (mm)
  rayoPlano(ndc, z) {
    this.raycaster.setFromCamera(ndc, this.camara);
    const pl = new THREE.Plane(new THREE.Vector3(0, 0, 1), -z * S);
    const p = new THREE.Vector3();
    if (!this.raycaster.ray.intersectPlane(pl, p)) return null;
    return [p.x / S, p.y / S, z];
  }
  // punto (mm) del rayo más cercano a una recta vertical por (x, y): para trazar montantes
  rayoVertical(ndc, x, y) {
    this.raycaster.setFromCamera(ndc, this.camara);
    const o = this.raycaster.ray.origin, d = this.raycaster.ray.direction;
    const P = new THREE.Vector3(x * S, y * S, 0), u = new THREE.Vector3(0, 0, 1);
    const w0 = o.clone().sub(P);
    const a = d.dot(d), b = d.dot(u), c = 1, dd = d.dot(w0), e = u.dot(w0);
    const den = a * c - b * b;
    if (Math.abs(den) < 1e-9) return null;
    const tz = (a * e - b * dd) / den;
    return [x, y, tz / S];
  }
  aPantalla(p) {
    const v = v3(p).project(this.camara);
    const r = this.renderer.domElement.getBoundingClientRect();
    return { x: ((v.x + 1) / 2) * r.width, y: ((1 - v.y) / 2) * r.height, z: v.z };
  }
  elegir(ndc) {
    this.raycaster.setFromCamera(ndc, this.camara);
    const objs = [...this.grupos.tramos.children, ...this.grupos.accesorios.children, ...this.grupos.equipos.children];
    const hits = this.raycaster.intersectObjects(objs, true).filter((h) => h.object.type === 'Mesh');
    for (const h of hits) {
      if (this.vista === 'planta' && !this.cortes.every((pl) => pl.distanceToPoint(h.point) >= -1e-4)) continue;
      let o = h.object;
      while (o && !o.userData.id) o = o.parent;
      if (o) return { id: o.userData.id, p: [h.point.x / S, h.point.y / S, h.point.z / S] };
    }
    return null;
  }
  captura() { return this.renderer.domElement.toDataURL('image/png'); }
}

export { familia };
