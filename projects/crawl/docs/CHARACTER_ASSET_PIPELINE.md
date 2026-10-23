# Character Asset Pipeline

## Toolchain

- Blender 5.2.0 LTS
- MPFB 2.0.17, build 20260722
- MakeHuman System Assets
- Unreal Engine 5.8.1
- Mutable core plugin enabled

## Rebuild

```powershell
Set-Location D:\CrawlTesting
.\scripts\build-underreach-mpfb-descenders.ps1
.\scripts\run-underreach-character-validation.ps1 `
  -SkipBlender `
  -UnrealEditorCmd "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
```

The DNA generator writes deterministic authoring inputs. Blender creates six
review images, `.blend` sources, joined skinned FBX meshes, five semantic clips
per species, and a digest manifest. Unreal clears the generated character
registry as a unit, imports each mesh with the legacy skeletal FBX path,
explicitly persists its Skeleton, imports clips, validates 21 contract bones,
face morph targets, and pose variation, and creates a Mutable asset scaffold.

The live bridge maps Human and Dwarf renderer manifests onto two accepted
skeletal presentation actors. Native meter rigs are converted by a disposable
actor scale, animation sections are duration-matched and overlap-trimmed, and
root-locked attacks continue through the measured contact validator. A
29A.1-only camera cue keeps the canonical opening strike visible; normal camera
director decisions and Feed receipts remain unchanged.

Generated reports live under
`unreal/CrawlPresentation/Generated/29a1`. The acceptance movie is rendered at
1920×1080, 60 fps. The generated map is presentation-only and may be rebuilt
from the accepted Alpha scene at any time.

## Mutable boundary

UE 5.8 Python can create the Customizable Object scaffold and exposes node
classes, but protects `CustomizableObject.Source`. The manual graph steps are
therefore documented separately; Character DNA and the Character Factory do
not depend on editor graph object IDs.
