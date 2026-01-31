import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { ThreeMFLoader } from "three/examples/jsm/loaders/3MFLoader.js";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

type MeshFormat = "3mf" | "ply" | "stl";
type Props = { url: string; height?: number; format?: MeshFormat };
type SectionRange = { min: number; max: number; step: number };
type SectionAxis = "X" | "Y" | "Z";

const ThreeMFViewer: React.FC<Props> = ({ url, height = 480, format = "3mf" }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const modelRef = useRef<THREE.Object3D | null>(null);
  const edgesRef = useRef<THREE.LineSegments[]>([]);
  const gridRef = useRef<THREE.GridHelper | null>(null);
  const axesRef = useRef<THREE.AxesHelper | null>(null);
  const clipPlaneRef = useRef<THREE.Plane | null>(null);
  const fitRef = useRef<{ distance: number; radius: number } | null>(null);
  const sectionBoundsRef = useRef<Record<SectionAxis, SectionRange> | null>(
    null
  );
  const measureGroupRef = useRef<THREE.Group | null>(null);
  const measurePointsRef = useRef<THREE.Vector3[]>([]);
  const resizeRef = useRef<(() => void) | null>(null);

  const [err, setErr] = useState<string | null>(null);
  const [edgesOn, setEdgesOn] = useState(true);
  const [wireframeOn, setWireframeOn] = useState(false);
  const [gridOn, setGridOn] = useState(false);
  const [axesOn, setAxesOn] = useState(false);
  const [autoRotate, setAutoRotate] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [sectionOn, setSectionOn] = useState(false);
  const [sectionAxis, setSectionAxis] = useState<SectionAxis>("Z");
  const [sectionOffset, setSectionOffset] = useState(0);
  const [sectionRange, setSectionRange] = useState<SectionRange | null>(null);
  const [sectionFlip, setSectionFlip] = useState(false);
  const [measureOn, setMeasureOn] = useState(false);
  const [measureValue, setMeasureValue] = useState<number | null>(null);

  const applyEdgesVisibility = (value: boolean) => {
    edgesRef.current.forEach((edge) => {
      edge.visible = value;
    });
  };

  const applyWireframe = (value: boolean) => {
    const model = modelRef.current;
    if (!model) return;
    model.traverse((child: any) => {
      if (child.isMesh && child.material) {
        const mats = Array.isArray(child.material)
          ? child.material
          : [child.material];
        mats.forEach((mat: any) => {
          if (mat && "wireframe" in mat) {
            mat.wireframe = value;
            mat.needsUpdate = true;
          }
        });
      }
    });
  };

  const updateClipPlane = (
    enabled: boolean,
    offset: number,
    axis: SectionAxis,
    flip: boolean
  ) => {
    const renderer = rendererRef.current;
    const plane = clipPlaneRef.current;
    if (!renderer || !plane) return;
    if (axis === "X") {
      plane.normal.set(1, 0, 0);
    } else if (axis === "Y") {
      plane.normal.set(0, 1, 0);
    } else {
      plane.normal.set(0, 0, 1);
    }
    plane.constant = -offset;
    if (flip) {
      plane.normal.multiplyScalar(-1);
      plane.constant = -plane.constant;
    }
    renderer.localClippingEnabled = enabled;
    renderer.clippingPlanes = enabled ? [plane] : [];
  };

  const updateSectionRangeForAxis = (axis: SectionAxis) => {
    const bounds = sectionBoundsRef.current;
    if (!bounds) return;
    setSectionRange(bounds[axis]);
    setSectionOffset(0);
  };

  const disposeSceneObject = (obj: THREE.Object3D) => {
    obj.traverse((child: any) => {
      if (child.geometry?.dispose) {
        child.geometry.dispose();
      }
      if (child.material) {
        const mats = Array.isArray(child.material)
          ? child.material
          : [child.material];
        mats.forEach((mat: any) => mat?.dispose?.());
      }
    });
  };

  const clearMeasureObjects = () => {
    const group = measureGroupRef.current;
    if (!group) return;
    while (group.children.length > 0) {
      const child = group.children[0];
      group.remove(child);
      disposeSceneObject(child);
    }
    measurePointsRef.current = [];
    setMeasureValue(null);
  };

  const addMeasureMarker = (point: THREE.Vector3) => {
    const group = measureGroupRef.current;
    if (!group) return;
    const radius = fitRef.current?.radius ?? 1;
    const markerSize = Math.max(radius * 0.01, 0.2);
    const geom = new THREE.SphereGeometry(markerSize, 16, 16);
    const mat = new THREE.MeshBasicMaterial({ color: 0xff6b00 });
    const marker = new THREE.Mesh(geom, mat);
    marker.position.copy(point);
    group.add(marker);
  };

  const addMeasureLine = (start: THREE.Vector3, end: THREE.Vector3) => {
    const group = measureGroupRef.current;
    if (!group) return;
    const geom = new THREE.BufferGeometry().setFromPoints([start, end]);
    const mat = new THREE.LineBasicMaterial({ color: 0xff6b00 });
    const line = new THREE.Line(geom, mat);
    group.add(line);
  };

  const fitToView = () => {
    const model = modelRef.current;
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    const scene = sceneRef.current;
    if (!model || !camera || !controls || !scene) return;

    const box = new THREE.Box3().setFromObject(model);
    if (box.isEmpty()) return;

    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    model.position.sub(center);

    const maxDim = Math.max(size.x, size.y, size.z);
    const radius = Math.max(maxDim * 0.5, 0.001);
    const fov = (camera.fov * Math.PI) / 180;
    let distance = radius / Math.tan(fov / 2);
    distance = Math.max(distance * 1.3, 0.5);

    camera.near = Math.max(0.01, distance / 200);
    camera.far = distance * 200;
    camera.updateProjectionMatrix();
    camera.position.set(distance, distance, distance);

    controls.minDistance = Math.max(0.01, radius * 0.2);
    controls.maxDistance = radius * 25;
    controls.target.set(0, 0, 0);
    controls.update();
    controls.saveState();

    fitRef.current = { distance, radius };

    const helperSize = Math.max(maxDim * 1.5, 10);
    if (gridRef.current) {
      scene.remove(gridRef.current);
    }
    const grid = new THREE.GridHelper(helperSize, 20, 0x888888, 0xdddddd);
    grid.visible = gridOn;
    gridRef.current = grid;
    scene.add(grid);

    if (axesRef.current) {
      scene.remove(axesRef.current);
    }
    const axes = new THREE.AxesHelper(Math.max(maxDim * 0.6, 5));
    axes.visible = axesOn;
    axesRef.current = axes;
    scene.add(axes);

    const halfX = Math.max(size.x * 0.5, 0.01);
    const halfY = Math.max(size.y * 0.5, 0.01);
    const halfZ = Math.max(size.z * 0.5, 0.01);
    const bounds = {
      X: { min: -halfX, max: halfX, step: Math.max(halfX / 60, 0.01) },
      Y: { min: -halfY, max: halfY, step: Math.max(halfY / 60, 0.01) },
      Z: { min: -halfZ, max: halfZ, step: Math.max(halfZ / 60, 0.01) },
    };
    sectionBoundsRef.current = bounds;
    setSectionRange(bounds[sectionAxis]);
    setSectionOffset(0);
  };

  const resetView = () => {
    const controls = controlsRef.current;
    if (controls) {
      controls.reset();
      controls.update();
    }
  };

  const setStandardView = (dir: THREE.Vector3) => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    const fit = fitRef.current;
    if (!camera || !controls) return;
    const distance = fit?.distance ?? 10;
    const v = dir.clone().normalize().multiplyScalar(distance);
    camera.position.set(v.x, v.y, v.z);
    controls.target.set(0, 0, 0);
    controls.update();
  };

  const zoomBy = (factor: number) => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;
    const dir = new THREE.Vector3()
      .copy(camera.position)
      .sub(controls.target)
      .multiplyScalar(factor);
    camera.position.copy(controls.target).add(dir);
    camera.updateProjectionMatrix();
    controls.update();
  };

  const toggleFullscreen = () => {
    const el = viewerRef.current;
    if (!el) return;
    if (!document.fullscreenElement) {
      el.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
  };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    setErr(null);
    container.innerHTML = "";

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xffffff);
    sceneRef.current = scene;

    const measureGroup = new THREE.Group();
    measureGroupRef.current = measureGroup;
    scene.add(measureGroup);
    measurePointsRef.current = [];
    setMeasureValue(null);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    const initialHeight = Math.max(container.clientHeight, height);
    renderer.setSize(container.clientWidth, initialHeight);
    renderer.setClearColor(0xffffff, 1);
    if ("outputColorSpace" in renderer) {
      (renderer as any).outputColorSpace = THREE.SRGBColorSpace;
    }
    rendererRef.current = renderer;
    container.appendChild(renderer.domElement);

    const camera = new THREE.PerspectiveCamera(
      45,
      container.clientWidth / initialHeight,
      0.1,
      10000
    );
    camera.position.set(2, 2, 2);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.screenSpacePanning = true;
    controls.autoRotate = autoRotate;
    controlsRef.current = controls;

    const hemi = new THREE.HemisphereLight(0xffffff, 0x666666, 0.9);
    scene.add(hemi);
    const dir = new THREE.DirectionalLight(0xffffff, 0.9);
    dir.position.set(6, 10, 8);
    scene.add(dir);
    const fill = new THREE.DirectionalLight(0xffffff, 0.4);
    fill.position.set(-6, -4, -6);
    scene.add(fill);

    const clipPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
    clipPlaneRef.current = clipPlane;
    updateClipPlane(sectionOn, sectionOffset, sectionAxis, sectionFlip);

    let model: THREE.Object3D | null = null;
    edgesRef.current = [];

    const onModelLoaded = (obj: THREE.Object3D) => {
      model = obj;
      modelRef.current = obj;
      scene.add(obj);

      const thresholdAngle = 20;
      obj.traverse((child: any) => {
        if (child.isMesh && child.geometry) {
          const edgeGeo = new THREE.EdgesGeometry(
            child.geometry,
            thresholdAngle
          );
          const edgeMat = new THREE.LineBasicMaterial({
            color: 0x000000,
            transparent: true,
            opacity: 0.7,
          });
          const edges = new THREE.LineSegments(edgeGeo, edgeMat);
          edges.visible = edgesOn;
          child.add(edges);
          edgesRef.current.push(edges);
        }
      });

      applyWireframe(wireframeOn);
      fitToView();
    };

    const buildMeshFromGeometry = (geometry: THREE.BufferGeometry) => {
      const hasNormals = !!geometry.getAttribute("normal");
      if (!hasNormals) {
        geometry.computeVertexNormals();
      }
      const hasColors = !!geometry.getAttribute("color");
      const material = new THREE.MeshStandardMaterial({
        color: hasColors ? 0xffffff : 0x9aa3b2,
        metalness: 0.1,
        roughness: 0.6,
        vertexColors: hasColors,
      });
      return new THREE.Mesh(geometry, material);
    };

    const onError = (e: any) =>
      setErr(`Failed to load 3D model: ${e?.message ?? "unknown error"}`);

    if (format === "3mf") {
      const loader = new ThreeMFLoader();
      loader.load(url, onModelLoaded, undefined, onError);
    } else if (format === "ply") {
      const loader = new PLYLoader();
      loader.load(
        url,
        (geometry) => onModelLoaded(buildMeshFromGeometry(geometry)),
        undefined,
        onError
      );
    } else {
      const loader = new STLLoader();
      loader.load(
        url,
        (geometry) => onModelLoaded(buildMeshFromGeometry(geometry)),
        undefined,
        onError
      );
    }

    const onResize = () => {
      if (!containerRef.current || !rendererRef.current || !cameraRef.current) {
        return;
      }
      const w = containerRef.current.clientWidth;
      const h = Math.max(containerRef.current.clientHeight, height);
      rendererRef.current.setSize(w, h);
      cameraRef.current.aspect = w / h;
      cameraRef.current.updateProjectionMatrix();
    };
    resizeRef.current = onResize;
    window.addEventListener("resize", onResize);

    let raf = 0;
    const tick = () => {
      controls.update();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    };
    tick();

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
          if (child.isLineSegments) {
            child.geometry?.dispose?.();
            const m = child.material;
            if (Array.isArray(m)) m.forEach((mm) => mm?.dispose?.());
            else m?.dispose?.();
          }
        });
      }

      gridRef.current?.geometry?.dispose?.();
      (gridRef.current as any)?.material?.dispose?.();
      axesRef.current?.geometry?.dispose?.();
      (axesRef.current as any)?.material?.dispose?.();
      if (measureGroupRef.current) {
        disposeSceneObject(measureGroupRef.current);
        scene.remove(measureGroupRef.current);
        measureGroupRef.current = null;
      }

      renderer.dispose();
      containerRef.current?.removeChild(renderer.domElement);
    };
  }, [url, height, format]);

  useEffect(() => {
    if (controlsRef.current) {
      controlsRef.current.autoRotate = autoRotate;
    }
  }, [autoRotate]);

  useEffect(() => {
    const onChange = () => {
      setIsFullscreen(document.fullscreenElement === viewerRef.current);
    };
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  useEffect(() => {
    if (!resizeRef.current) return;
    const id = requestAnimationFrame(() => resizeRef.current?.());
    return () => cancelAnimationFrame(id);
  }, [isFullscreen]);

  useEffect(() => {
    if (gridRef.current) gridRef.current.visible = gridOn;
  }, [gridOn]);

  useEffect(() => {
    if (axesRef.current) axesRef.current.visible = axesOn;
  }, [axesOn]);

  useEffect(() => {
    applyEdgesVisibility(edgesOn);
  }, [edgesOn]);

  useEffect(() => {
    applyWireframe(wireframeOn);
  }, [wireframeOn]);

  useEffect(() => {
    updateClipPlane(sectionOn, sectionOffset, sectionAxis, sectionFlip);
  }, [sectionOn, sectionOffset, sectionAxis, sectionFlip]);

  useEffect(() => {
    updateSectionRangeForAxis(sectionAxis);
  }, [sectionAxis]);

  useEffect(() => {
    if (!measureOn) {
      clearMeasureObjects();
      return;
    }
    clearMeasureObjects();

    const renderer = rendererRef.current;
    const camera = cameraRef.current;
    if (!renderer || !camera) return;

    const dom = renderer.domElement;
    const onClick = (event: MouseEvent) => {
      if (!rendererRef.current || !cameraRef.current || !modelRef.current) {
        return;
      }
      const rect = dom.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera({ x, y }, cameraRef.current);
      const hits = raycaster.intersectObject(modelRef.current, true);
      if (!hits.length) return;
      const point = hits[0].point.clone();

      if (measurePointsRef.current.length >= 2) {
        clearMeasureObjects();
      }

      measurePointsRef.current.push(point);
      addMeasureMarker(point);

      if (measurePointsRef.current.length === 2) {
        const [p1, p2] = measurePointsRef.current;
        addMeasureLine(p1, p2);
        setMeasureValue(p1.distanceTo(p2));
      }
    };

    dom.addEventListener("click", onClick);
    return () => {
      dom.removeEventListener("click", onClick);
    };
  }, [measureOn, url, format]);

  const btnBase: React.CSSProperties = {
    fontSize: 12,
    padding: "2px 6px",
    borderRadius: 4,
    border: "1px solid #c8c8c8",
    background: "#f7f7f7",
    cursor: "pointer",
  };

  const toggleStyle = (active: boolean): React.CSSProperties => ({
    ...btnBase,
    background: active ? "#1f6feb" : btnBase.background,
    borderColor: active ? "#1f6feb" : "#c8c8c8",
    color: active ? "#ffffff" : "#333333",
  });

  const viewerStyle: React.CSSProperties = {
    position: "relative",
    width: isFullscreen ? "100vw" : "100%",
    height: isFullscreen ? "100vh" : height,
    background: "#ffffff",
    overflow: "hidden",
  };

  return (
    <div>
      {err ? (
        <div className="alert alert-danger" role="alert">
          {err}
        </div>
      ) : (
        <div ref={viewerRef} style={viewerStyle}>
          <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
          <div
            style={{
              position: "absolute",
              left: 8,
              right: 8,
              bottom: 8,
              display: "flex",
              flexWrap: "wrap",
              gap: 8,
              padding: 8,
              borderRadius: 6,
              border: "1px solid #e2e2e2",
              background: "rgba(255,255,255,0.9)",
              alignItems: "center",
              zIndex: 2,
            }}
          >
            <button style={btnBase} type="button" onClick={fitToView}>
              Fit
            </button>
            <button style={btnBase} type="button" onClick={resetView}>
              Reset
            </button>
            <button
              style={btnBase}
              type="button"
              onClick={() => setStandardView(new THREE.Vector3(0, 0, 1))}
            >
              Front
            </button>
            <button
              style={btnBase}
              type="button"
              onClick={() => setStandardView(new THREE.Vector3(1, 0, 0))}
            >
              Right
            </button>
            <button
              style={btnBase}
              type="button"
              onClick={() => setStandardView(new THREE.Vector3(0, 1, 0))}
            >
              Top
            </button>
            <button
              style={btnBase}
              type="button"
              onClick={() => setStandardView(new THREE.Vector3(1, 1, 1))}
            >
              Iso
            </button>
            <button style={btnBase} type="button" onClick={() => zoomBy(0.8)}>
              Zoom +
            </button>
            <button style={btnBase} type="button" onClick={() => zoomBy(1.25)}>
              Zoom -
            </button>
            <button
              style={toggleStyle(gridOn)}
              type="button"
              onClick={() => setGridOn((v) => !v)}
            >
              Grid
            </button>
            <button
              style={toggleStyle(axesOn)}
              type="button"
              onClick={() => setAxesOn((v) => !v)}
            >
              Axes
            </button>
            <button
              style={toggleStyle(edgesOn)}
              type="button"
              onClick={() => setEdgesOn((v) => !v)}
            >
              Edges
            </button>
            <button
              style={toggleStyle(wireframeOn)}
              type="button"
              onClick={() => setWireframeOn((v) => !v)}
            >
              Wireframe
            </button>
            <button
              style={toggleStyle(sectionOn)}
              type="button"
              onClick={() => setSectionOn((v) => !v)}
            >
              Section
            </button>
            {sectionOn && sectionRange ? (
              <>
                <span style={{ fontSize: 12, color: "#444" }}>Axis</span>
                <button
                  style={toggleStyle(sectionAxis === "X")}
                  type="button"
                  onClick={() => setSectionAxis("X")}
                >
                  X
                </button>
                <button
                  style={toggleStyle(sectionAxis === "Y")}
                  type="button"
                  onClick={() => setSectionAxis("Y")}
                >
                  Y
                </button>
                <button
                  style={toggleStyle(sectionAxis === "Z")}
                  type="button"
                  onClick={() => setSectionAxis("Z")}
                >
                  Z
                </button>
                <button
                  style={toggleStyle(sectionFlip)}
                  type="button"
                  onClick={() => setSectionFlip((v) => !v)}
                >
                  Flip
                </button>
                <span style={{ fontSize: 12, color: "#444" }}>Offset</span>
                <input
                  type="range"
                  min={sectionRange.min}
                  max={sectionRange.max}
                  step={sectionRange.step}
                  value={sectionOffset}
                  onChange={(e) => setSectionOffset(Number(e.target.value))}
                  style={{ width: 200 }}
                />
              </>
            ) : null}
            <button
              style={toggleStyle(autoRotate)}
              type="button"
              onClick={() => setAutoRotate((v) => !v)}
            >
              Auto-rotate
            </button>
            <button
              style={toggleStyle(isFullscreen)}
              type="button"
              onClick={toggleFullscreen}
            >
              Full screen
            </button>
            <button
              style={toggleStyle(measureOn)}
              type="button"
              onClick={() => setMeasureOn((v) => !v)}
            >
              Measure
            </button>
            {measureOn ? (
              <span style={{ fontSize: 12, color: "#333" }}>
                {measureValue === null
                  ? "Measure: click two points"
                  : `Measure: ${measureValue.toFixed(2)}`}
              </span>
            ) : null}
            <span style={{ fontSize: 11, color: "#666" }}>
              Drag to rotate, right drag to pan, wheel to zoom
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ThreeMFViewer;
