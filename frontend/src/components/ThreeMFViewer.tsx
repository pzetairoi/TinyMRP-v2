import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { ThreeMFLoader } from "three/examples/jsm/loaders/3MFLoader.js";

type Props = { url: string; height?: number };

const ThreeMFViewer: React.FC<Props> = ({ url, height = 480 }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);
    scene.background = new THREE.Color(0xffffff);       // ← white

    // renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(containerRef.current.clientWidth, height);
    renderer.setClearColor(0xffffff, 1);  
    containerRef.current.appendChild(renderer.domElement);

    // camera
    const camera = new THREE.PerspectiveCamera(
      45,
      containerRef.current.clientWidth / height,
      0.1,
      10000
    );
    camera.position.set(2, 2, 2);

    // controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    // lights
    scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 0.8));
    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(5, 10, 7.5);
    scene.add(dir);

    // load 3MF
    const loader = new ThreeMFLoader();
    let model: THREE.Object3D | null = null;


    // 2) After the 3MF model loads (inside loader.load success callback),
//    add an Edges overlay to each mesh
loader.load(
  url,
  (obj) => {
    model = obj;

    // center & fit (your existing code) …
    const box = new THREE.Box3().setFromObject(obj);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    obj.position.sub(center);
    scene.add(obj);

    // camera fit (your existing code) …
    const maxDim = Math.max(size.x, size.y, size.z);
    const fov = camera.fov * (Math.PI / 180);
    let camDist = maxDim / (2 * Math.tan(fov / 2));
    camDist *= 1.5;
    camera.position.set(camDist, camDist, camDist);
    controls.target.set(0, 0, 0);
    controls.update();

    // ⬇️ Draw edges (adjust thresholdAngle for how “busy” the edges are)
    const thresholdAngle = 20; // degrees; smaller = more edges
    obj.traverse((child: any) => {
      if (child.isMesh && child.geometry) {
        const edgeGeo = new THREE.EdgesGeometry(child.geometry, thresholdAngle);
        const edgeMat = new THREE.LineBasicMaterial({
          color: 0x000000,
          transparent: true,
          opacity: 0.7,
        });
        const edges = new THREE.LineSegments(edgeGeo, edgeMat);
        // attach to the mesh so it follows transforms
        child.add(edges);
      }
    });
  },
  undefined,
  (e) => setErr(`Failed to load 3D model: ${e?.message ?? "unknown error"}`)
);


    // resize
    const onResize = () => {
      if (!containerRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = height;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    window.addEventListener("resize", onResize);

    // render loop
    let raf = 0;
    const tick = () => {
      controls.update();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    };
    tick();

    // cleanup
// 3) Cleanup: also dispose LineSegments (edges) we added
return () => {
  cancelAnimationFrame(raf);
  window.removeEventListener("resize", onResize);
  controls.dispose();

  if (model) {
    model.traverse((child: any) => {
      if (child.isMesh) {
        child.geometry?.dispose?.();
        const m = child.material;
        if (Array.isArray(m)) m.forEach((mm) => mm?.dispose?.());
        else m?.dispose?.();
      }
      if (child.isLineSegments) {                 // ← dispose edge overlays
        child.geometry?.dispose?.();
        const m = child.material;
        if (Array.isArray(m)) m.forEach((mm) => mm?.dispose?.());
        else m?.dispose?.();
      }
    });
  }

  renderer.dispose();
  containerRef.current?.removeChild(renderer.domElement);
};
  }, [url, height]);

  return (
    <div>
      {err ? (
        <div className="alert alert-danger" role="alert">{err}</div>
      ) : (
        <div ref={containerRef} style={{ width: "100%", height }} />
      )}
    </div>
  );
};

export default ThreeMFViewer;
