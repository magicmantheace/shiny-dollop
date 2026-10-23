# Character Asset Provenance

| Asset | Source/creator | License | Local/Unreal use | Modifications |
|---|---|---|---|---|
| MPFB base body, eyes, hair, garments | MakeHuman Community, [System Assets](https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_assets.html) | CC0 / pack metadata | MPFB library → generated FBX → `/Game/Underreach29A1/Characters` | Deterministic morphing, joining, rigging, materials, semantic animation |
| Helmet proxy | Underreach project | Project-authored proxy | `internal://29a1/Helmet_Proxy` | Deterministic rigid fitting |
| Breastplate proxy | Underreach project | Project-authored proxy | `internal://29a1/Breastplate_Proxy` | Deterministic rigid fitting |
| Sword proxy | Underreach project | Project-authored proxy | `internal://29a1/Sword_Proxy` | Right-hand attachment and attack proof |
| Beard proxies | Underreach project | Project-authored proxy | `internal://29a1/beard/*` | Human/Dwarf deterministic variants |

Structured provenance is validated by `AssetProvenance` in
`src/livingworld/character_factory.py`. No account-gated or Fab assets were
downloaded or redistributed in 29A.1.
