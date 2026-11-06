import { useEffect, useRef, useState, type ReactNode } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import type { PetAnimState } from './visual-state.js';
import { computePose, dampPose, type PetPose } from './pose-driver.js';
import glbUrl from './assets/pip-3d.glb';

/**
 * The rigged 3D Pip (royal fur only — the Meshy model of the owner's
 * pet, rigged in Blender with a 14-bone armature). Bones are posed
 * procedurally from the pet's animation state by pose-driver.ts; there
 * are no baked clips. Any failure (no WebGL, model load error) falls
 * back to the painterly portrait the caller supplies, so the pet is
 * never a black square.
 */

const BONE_NAMES = [
  'root',
  'head',
  'ear.L',
  'ear.R',
  'wing.L',
  'wing2.L',
  'wing.R',
  'wing2.R',
  'tail.2',
  'tail.3',
] as const;

interface Rig {
  bones: Map<string, THREE.Bone>;
  restQuat: Map<string, THREE.Quaternion>;
  rootRestY: number;
}

function collectRig(root: THREE.Object3D): Rig {
  const bones = new Map<string, THREE.Bone>();
  const restQuat = new Map<string, THREE.Quaternion>();
  root.traverse((o) => {
    if ((o as THREE.Bone).isBone && (BONE_NAMES as readonly string[]).includes(o.name)) {
      bones.set(o.name, o as THREE.Bone);
      restQuat.set(o.name, o.quaternion.clone());
    }
  });
  const rootBone = bones.get('root');
  return { bones, restQuat, rootRestY: rootBone ? rootBone.position.y : 0 };
}

const _q = new THREE.Quaternion();
const _axisX = new THREE.Vector3(1, 0, 0);
const _axisY = new THREE.Vector3(0, 1, 0);
const _axisZ = new THREE.Vector3(0, 0, 1);

function pitch(rig: Rig, name: string, angle: number) {
  const bone = rig.bones.get(name);
  const rest = rig.restQuat.get(name);
  if (!bone || !rest || angle === 0) return;
  _q.setFromAxisAngle(_axisX, angle);
  bone.quaternion.copy(rest).multiply(_q);
}

function applyPose(rig: Rig, pose: PetPose) {
  const root = rig.bones.get('root');
  if (root) {
    root.position.y = rig.rootRestY + pose.rootY;
    const rest = rig.restQuat.get('root');
    if (rest && pose.sway !== 0) {
      _q.setFromAxisAngle(_axisZ, pose.sway);
      root.quaternion.copy(rest).multiply(_q);
    }
  }
  pitch(rig, 'head', pose.headPitch);
  pitch(rig, 'ear.L', pose.earPitch);
  pitch(rig, 'ear.R', pose.earPitch);
  pitch(rig, 'wing.L', pose.wingPitch);
  pitch(rig, 'wing.R', pose.wingPitch);
  pitch(rig, 'wing2.L', pose.wing2Pitch);
  pitch(rig, 'wing2.R', pose.wing2Pitch);
  for (const [name, scale] of [['tail.2', 1], ['tail.3', 1.4]] as const) {
    const bone = rig.bones.get(name);
    const rest = rig.restQuat.get(name);
    if (bone && rest && pose.tailYaw !== 0) {
      _q.setFromAxisAngle(_axisY, pose.tailYaw * scale);
      bone.quaternion.copy(rest).multiply(_q);
    }
  }
}

export function PetArt3D({
  anim,
  fallback,
}: {
  anim: PetAnimState;
  fallback: ReactNode;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const animRef = useRef(anim);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    animRef.current = anim;
  }, [anim]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setFailed(true);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(host.clientWidth, host.clientHeight);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      35,
      host.clientWidth / Math.max(1, host.clientHeight),
      0.1,
      50,
    );
    camera.position.set(0.35, 1.02, 3.55);
    camera.lookAt(0, 0.84, 0);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x7a5cff, 0.85));
    const key = new THREE.DirectionalLight(0xffffff, 2.0);
    key.position.set(2.5, 3.2, 3.0);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xbfd4ff, 0.5);
    rim.position.set(-2.5, 1.5, -2.0);
    scene.add(rim);

    let rig: Rig | null = null;
    let disposed = false;
    const loader = new GLTFLoader();
    loader
      .loadAsync(glbUrl)
      .then((gltf) => {
        if (disposed) return;
        scene.add(gltf.scene);
        rig = collectRig(gltf.scene);
      })
      .catch(() => {
        if (!disposed) setFailed(true);
      });

    const clock = new THREE.Clock();
    let pose: PetPose = computePose('idle', 0);
    let raf = 0;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      const dt = Math.min(clock.getDelta(), 0.05);
      if (rig) {
        pose = dampPose(pose, computePose(animRef.current, clock.elapsedTime), dt);
        applyPose(rig, pose);
      }
      renderer.render(scene, camera);
    };
    tick();

    const onResize = () => {
      const w = host.clientWidth;
      const h = Math.max(1, host.clientHeight);
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    window.addEventListener('resize', onResize);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', onResize);
      scene.traverse((o) => {
        const mesh = o as THREE.Mesh;
        if (mesh.isMesh) {
          mesh.geometry.dispose();
          const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
          for (const m of mats) {
            const mat = m as THREE.MeshStandardMaterial;
            mat.map?.dispose();
            mat.dispose();
          }
        }
      });
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  if (failed) return <>{fallback}</>;
  return <div className="pet-art pet-3d" ref={hostRef} />;
}
