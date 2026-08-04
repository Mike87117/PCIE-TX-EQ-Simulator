"""
Developer debug helper for manually inspecting PCIe Gen6 visualization presets.
"""

from pcie_eq.tx_eq import (
    PCIE_GEN6_PRESET_TAP_TABLE,
    calc_gen6_levels,
)

__all__ = ["validate_gen6_presets"]


def validate_gen6_presets():
    """Developer debug helper for manually inspecting Gen6 visualization presets."""
    header = (
        "Preset  C-2     C-1      C0      C+1      Va      Vb      "
        "Vc1     Vc2     Vd      Va/Vd   Vb/Vd   Vc1/Vd  Vc2/Vd  "
        "Pre1    Pre2    De      Boost   TapSum"
    )
    print(header)
    print("-" * len(header))
    for preset_name in sorted(
        PCIE_GEN6_PRESET_TAP_TABLE,
        key=lambda name: int(name[1:]),
    ):
        cm2, cm1, cp1 = PCIE_GEN6_PRESET_TAP_TABLE[preset_name]
        (
            c0,
            va,
            vb,
            vc1,
            vc2,
            vd,
            pre1_db,
            pre2_db,
            de_db,
            boost_db,
        ) = calc_gen6_levels(cm2, cm1, cp1)
        tap_sum = abs(cm2) + abs(cm1) + abs(c0) + abs(cp1)
        if vd > 0:
            va_ratio = f"{va / vd:7.3f}"
            vb_ratio = f"{vb / vd:7.3f}"
            vc1_ratio = f"{vc1 / vd:7.3f}"
            vc2_ratio = f"{vc2 / vd:7.3f}"
        else:
            va_ratio = vb_ratio = vc1_ratio = vc2_ratio = "    N/A"
        print(
            f"{preset_name:<6} "
            f"{cm2:6.3f} {cm1:7.3f} {c0:7.3f} {cp1:7.3f} "
            f"{va:7.3f} {vb:7.3f} {vc1:7.3f} {vc2:7.3f} {vd:7.3f} "
            f"{va_ratio} {vb_ratio} {vc1_ratio} {vc2_ratio} "
            f"{pre1_db:7.2f} {pre2_db:7.2f} {de_db:7.2f} {boost_db:7.2f} "
            f"{tap_sum:7.3f}"
        )
