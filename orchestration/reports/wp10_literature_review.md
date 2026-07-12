# WP10 local literature review: utility pathways into CMP

Date: 2026-07-11  
Task: T-WP10  
Review plane: locally supplied scientific papers  
Purpose: determine which utility-to-CMP pathways have qualitative literature support and which transfer functions must remain synthetic

## Review boundary

The user supplied ten PDF files in `fetched_papers/`. This review uses those
local copies only. It does not infer redistribution permission or a separate
licence from possession of a file. No paper is copied into a public-data
artifact, and no experimental value is silently transferred into the
simulator. SHA-256 identifies the exact reviewed bytes.

The review asks four narrow questions:

1. Is water physically used in a CMP operation capable of affecting later or
   concurrent removal?
2. Is a dynamic pad/thermal/slurry state scientifically preferable to a direct
   UPW-to-MRR multiplier?
3. Does any reviewed study calibrate facility-header pressure or flow
   thresholds for a CMP tool?
4. Which proposed connections must remain structural uncertainty cases?

## Reviewed corpus and disposition

| Local file | SHA-256 | Main contribution used here | WP10 disposition |
|---|---|---|---|
| `bahr2017.pdf` | `ca1048d99a9ee0182b5d032a466e2093e48589fd48c5a7328878dd2fdf16e34f` | Bahr et al., *Micromachines* 8, 170, DOI 10.3390/mi8060170: UPW rinses the pad between polishes; residual rinse water, spent slurry, injection position, mixing, and fresh-slurry availability affect removal rate. | Supports a rinse/slurry-mixing pathway qualitatively. It also shows why the sign is not safely monotone: less rinse water can reduce dilution while also changing debris/spent-slurry removal. It does not support a generic positive UPW-flow-to-MRR law. |
| `borucki2002.pdf` | `d8ffa396a696b108aa5b5f1dad7c7aace90a39f4ade4ede43a425e1d80459c6e` | Borucki, *Journal of Engineering Mathematics* 43, 105–114: unconditioned pad asperity wear changes real contact area and causes polish-rate decay; water plasticizes polyurethane and pad modulus is temperature-sensitive. | Supports a stored pad-surface state and delayed MRR response. It supplies no facility-water transient coefficient. |
| `borucki2004.pdf` | `6fad63b059d596c96e0d167fe19fec4a59d54b08a844963c536c7b997181eef7` | Borucki et al., *Journal of Engineering Mathematics* 50, 1–24: statistical/PDE models combine pad conditioning and polishing wear for solid and foamed pads. | Supports separate conditioning and wear terms plus state memory; too detailed and insufficiently parameterized for direct adoption in this PoC. |
| `chang2007.pdf` | `df782ef6a1de04b89e794eedd5a65c947c25c5da986721c263c9ba1c80bbb3fc` | Chang et al., *Microelectronic Engineering*, DOI 10.1016/j.mee.2006.11.011: conditioning kinematics and pad-wear profiles affect pad shape and polishing performance. | Supports explicit DRESS behavior and consumable evolution, not a UPW transfer function. |
| `hocheng2000.pdf` | `6edaba2643af6b1da577c6e0dc4eb60be25f573406a8a6985fe6eeaffdc94219` | Hocheng et al.: kinematic variables and Preston-type removal structure. | Supports the already frozen WP08 pressure–velocity exposure. It provides no water-utility topology calibration. |
| `kim2005.pdf` | `5d69e6b7bab7029eef36ce6d547a6aafccec22918ae02dd8f480d8de4c601b4b` | Kim et al., *Microelectronic Engineering* 82, 680–685, DOI 10.1016/j.mee.2005.07.080: diamond conditioning is performed using DI water; changing conditioning-water temperature changed grooves/pores and subsequent oxide removal in that apparatus and material system. | Strong qualitative support that a DI-water conditioning boundary can affect later removal. The numerical temperature/MRR values are material- and tool-specific and are not imported. Flow and header pressure were not varied. |
| `kim2017.pdf` | `ed9e901f5198de49358c06a8d63229a794ae324b879eda56f7bc49721607e32b` | Kim et al., *Wear*, DOI 10.1016/j.wear.2017.07.019: frictional heating, pad mechanical-property changes, conditioner wear, and pad-conditioning performance are linked; the study reports strong pad-property changes at elevated W-CMP temperatures. | Supports temperature-dependent pad/conditioning physics and thermal uncertainty. It does not establish that facility UPW directly reaches the pad or calibrate a header-temperature gain. |
| `mudhivarthi2006.pdf` | `92995c9843b426e8de15b9049cf7cb74a91cbe2d43a08254af9a0b4a329f211e` | Mudhivarthi et al., *Journal of The Electrochemical Society* 153, G372–G378, DOI 10.1149/1.2177007: slurry flow affects pad temperature and copper removal; ex-situ conditioning used a fixed water flow while water temperature was varied, changing conditioning behavior and subsequent polishing. | Supports distinct slurry-flow, thermal, and water-conditioning pathways. Because conditioning-water flow was fixed, it does not calibrate loss-of-water availability. Defect outcomes discussed by the paper are outside this project’s validated claims. |
| `sun2010.pdf` | `a8de4976347e68c92bb9000506a2a666616c9e9c34f6a2a2c3251ce4a421eda7` | Sun et al., *Microelectronic Engineering*, DOI 10.1016/j.mee.2009.08.007: conditioner diamond size and force change pad surface/conditioning performance. | Supports conditioner effectiveness as a separate consumable state. No UPW coefficient is available. |
| `white2003.pdf` | `45b71d43f4d49208184cce43f482e42335ca210ed1f27ffc62ee57b2452ce1f8` | White et al., *Journal of The Electrochemical Society* 150, G271–G278, DOI 10.1149/1.1560642: a lumped energy balance represents frictional/chemical input, pad/slurry storage, and slurry heat removal proportional to mass flow and heat capacity. | Supports the WP08 interface energy balance and a physically declared thermal connection. It models slurry/pad heat transfer, not a facility-UPW heat exchanger. |

## Findings by pathway

### Dressing-water support

DI water is explicitly used during pad conditioning in Kim et al. (2005), and
Mudhivarthi et al. (2006) reports ex-situ conditioning with water before
subsequent polishing. Borucki (2002, 2004), Chang et al. (2007), and Sun et al.
(2010) show why a conditioning perturbation should persist through pad surface
state rather than enter MRR algebraically.

This establishes a plausible topology:

```text
UPW service at a declared conditioning branch
→ realized conditioning activity during DRESS
→ stored pad-surface activity
→ subsequent POLISH MRR
```

It does **not** establish the transient map from facility supply pressure and
flow to realized conditioning. That map is an engineering approximation with
synthetic thresholds and must be subjected to zero-link, topology, and
parameter sensitivity.

### Rinse/slurry interaction

Bahr et al. (2017) provides direct evidence that UPW rinse water can remain on
the pad, mix with fresh slurry, and change removal through dilution and slurry
availability. However, reduced rinsing cannot be assigned a universal MRR sign:
residual-water dilution, spent-slurry removal, pad debris, residence time, and
fresh-slurry fraction change together. A single monotone UPW-rinse multiplier
would therefore be scientifically misleading.

WP10 does not implement a rinse-quality or debris state. The only direct
slurry-support option is named `SYNTHETIC_SLURRY_SUPPORT`, carries no claim of
real tool plumbing, and exists to test structural sensitivity.

### Thermal loop

White et al. (2003), Kim et al. (2017), and Mudhivarthi et al. (2006) support
dynamic heat storage/removal and temperature-sensitive CMP behavior. They do
not demonstrate that the modeled facility UPW header is the coolant source for
the target CMP tool. `THERMAL_LOOP` is therefore a conditional connection that
is physically meaningful only when declared plumbing exists. The default WP08
temperature-to-MRR coefficient remains zero, so thermal coupling changes a
simulated temperature state but has exactly zero MRR effect unless a separately
named synthetic material profile is selected.

### No connection

No reviewed paper establishes the actual plumbing of the PHM challenge tool,
nor paired facility electrical/UPW and CMP metrology. `NO_CONNECTION` is
therefore the repository default and a mandatory structural negative control.
Zero link strength must also be present inside each connected topology’s
uncertainty ensemble.

## Unsupported inferences explicitly rejected

The reviewed papers do not support any of the following:

- a universal facility-header supply-pressure threshold for CMP;
- a universal conditioning-water flow threshold;
- direct use of UPW water-quality proxy as an MRR modifier;
- a generic instantaneous UPW-to-MRR multiplier;
- transfer of material-specific temperature/MRR values to the PHM tool;
- a claim that a 25% grid sag for 400 ms must produce a CMP excursion;
- prevention or prediction of scratches, dishing, erosion, particles, yield
  loss, equipment damage, or production behavior.

## Design consequence

The narrowest defensible primary WP10 topology is delayed dressing-water
support. The coupler will translate validated latent UPW pressure/flow into a
bounded dressing-availability boundary only when that topology is explicitly
selected. The CMP subsystem then supplies the memory through its existing pad
surface state. Thermal and synthetic slurry-support structures remain
sensitivity cases; no connection remains the default. Every numerical
threshold and link strength is synthetic and must be reported as such.
