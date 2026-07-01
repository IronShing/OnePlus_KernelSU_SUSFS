# RedMagic 11 Pro NX809J Packaging Guide

This document records the known-working packaging flow used for the RedMagic 11 Pro / NX809J tests.

## Camera Pin-Sharing Fix (main rear camera)

The NX809J's main rear camera (ov50e40) and its EEPROM share the same MCLK pin
(GPIO_91) and the same `CAM_VIO` regulator gpio (533). Upstream GKI 6.12 pinctrl
and gpiolib enforce strict single ownership, so the EEPROM's second claim fails
with `-EBUSY` (`pin GPIO_91 already requested ... cannot claim`,
`cam_res_mgr_gpio_request: gpio 533 fails -16`) — the sensor never powers up and
`vendor.qti.camera.provider` crashes, so the main sensor cannot be opened at all.

The stock Nubia downstream kernel refcount-shared these. The fix is a small
kernel-source patch (`configs/patches/nx809j-camera-pin-sharing.patch`, touching
`drivers/pinctrl/pinmux.c` and `drivers/gpio/gpiolib.c`) that restores the
sharing. It is applied during the CI build when the device config sets
`"cam_pin_share": true` (enabled in `configs/a16/OP15.json`, the config used for
the NX809J build). The patch is a no-op on hardware whose device tree does not
share these pins (e.g. the OnePlus 15), because the shared-claim code paths are
only reached when two sub-devices request the same pin/gpio.

The working kernel image is the original WildKernels OP15 image from:

`AK3_OP15_OOS16_android16-6.12.23_KSUN_33169_SuSFS_v2.1.0.zip`

Known-working `Image` SHA256:

`6464D52AA83B9B969E6AD62A506E8F802ECFBFDDCB434C2258CB3F737BBBD00B`

The rebuilt GitHub Actions image is not the same image and should be treated as experimental until it passes the same RAM boot and permanent flash checks.

## Final ZIPs

Two ZIPs are used:

- AnyKernel flash package: flashes the OP-WILD kernel image.
- Droidspaces KernelSU module: starts Droidspaces daemon and run-at-boot containers.

Known package hashes from the first fixed build:

- `AK3_RedMagic11Pro_NX809J_WILD_ORIGINAL_6.12.23_KSUN_SuSFS_v2.1.0_EXEC_20260607_212809.zip`
  - Size: `19823318`
  - SHA256: `9F260C080EB0ABF548DE6C701AF9DD41902EAE9EF54D31DE25AD47754C716915`
- `Droidspaces_Daemon_Init_KernelSU_v6.2.5_NX809J_20260607_213359.zip`
  - Size: `1694994`
  - SHA256: `002DD21332B3F09E60EB5E5F3D2189822273BC9432F7165BCE69D7F6F3138FDF`

## Why Packaging Matters

Do not create the ZIP with `Compress-Archive` on Windows.

That can strip Unix executable bits from:

- `META-INF/com/google/android/update-binary`
- `anykernel.sh`
- `tools/*`
- `post-fs-data.sh`
- `service.sh`
- Droidspaces payload binaries

If those permissions are lost, Kernel Flasher or KernelSU may fail before the actual install logic runs.

Validate with:

```powershell
tar -tvf .\package.zip
```

Expected examples:

```text
-rwxr-xr-x ... META-INF/com/google/android/update-binary
-rwxr-xr-x ... anykernel.sh
-rwxr-xr-x ... tools/magiskboot
-rwxr-xr-x ... post-fs-data.sh
-rwxr-xr-x ... service.sh
```

## Generate AnyKernel

Inputs:

- Template ZIP: official WildKernels OP15 AnyKernel ZIP.
- AK3 tree: unpacked tree containing the fixed `anykernel.sh`, original working `Image`, and `OP15_OOS16.txt`.

Command:

```powershell
python .\tools\nx809j\package_anykernel.py `
  --template-zip C:\Users\adriano\Videos\kernelsusfs\AK3_OP15_OOS16_android16-6.12.23_KSUN_33169_SuSFS_v2.1.0.zip `
  --ak3-tree C:\Users\adriano\Videos\kernelsusfs\redmagic11pro_minimal_wild_original_fixed\ak3_tree `
  --output C:\Users\adriano\Videos\kernelsusfs\generated_anykernel\AK3_RedMagic11Pro_NX809J_WILD_ORIGINAL.zip
```

The fixed `anykernel.sh` must include:

```sh
do.check_boot_version=1
```

and the GKI check must accept `6.12*`:

```sh
case $kernel_version in
    5.1*) ksu_supported=true ;;
    6.1*) ksu_supported=true ;;
    6.6*) ksu_supported=true ;;
    6.12*) ksu_supported=true ;;
    *) ksu_supported=false ;;
esac
```

The install section also hardens tool permissions before flashing:

```sh
sync
sleep 0.5
chmod -R 755 "${AKHOME}/tools"
```

## Generate Droidspaces KernelSU Module

Inputs:

- Official Droidspaces boot-module assets from `ravindu644/Droidspaces-OSS`:
  - `module.prop`
  - `post-fs-data.sh`
  - `service.sh`
  - `sepolicy.rule`
- Droidspaces payload binaries:
  - `droidspaces`
  - `busybox`
  - `magiskpolicy`

If pulling payload binaries from the phone:

```powershell
adb shell "su -c 'rm -rf /sdcard/Download/droidspaces_module_payload; mkdir -p /sdcard/Download/droidspaces_module_payload; cp -f /data/local/Droidspaces/bin/droidspaces /sdcard/Download/droidspaces_module_payload/; cp -f /data/local/Droidspaces/bin/busybox /sdcard/Download/droidspaces_module_payload/; cp -f /data/local/Droidspaces/bin/magiskpolicy /sdcard/Download/droidspaces_module_payload/; chmod 644 /sdcard/Download/droidspaces_module_payload/*'"
adb pull /sdcard/Download/droidspaces_module_payload C:\Users\adriano\Videos\kernelsusfs\droidspaces_module_payload
```

Package:

```powershell
python .\tools\nx809j\package_droidspaces_module.py `
  --boot-module-dir C:\Users\adriano\Videos\kernelsusfs\Droidspaces-OSS_official\Android\app\src\main\assets\boot-module `
  --payload-bin-dir C:\Users\adriano\Videos\kernelsusfs\droidspaces_module_payload `
  --output C:\Users\adriano\Videos\kernelsusfs\generated_modules\Droidspaces_Daemon_Init_KernelSU.zip
```

Install by KernelSU CLI:

```powershell
adb push .\Droidspaces_Daemon_Init_KernelSU.zip /sdcard/Download/kernel_fixed/
adb shell "su -c '/data/adb/ksud module install /sdcard/Download/kernel_fixed/Droidspaces_Daemon_Init_KernelSU.zip'"
adb reboot
```

After reboot:

```powershell
adb shell "su -c '/data/adb/ksud module list'"
adb shell "su -c 'ps -A -o USER,PID,PPID,NAME,ARGS | grep -i droidspaces'"
adb shell "su -c '/data/local/Droidspaces/bin/droidspaces check'"
```

## Compile From GitHub Actions

The fork is configured with:

- `origin`: `https://github.com/Coding-BR/OnePlus_KernelSU_SUSFS.git`
- `upstream`: `https://github.com/WildKernels/OnePlus_KernelSU_SUSFS.git`

To compile from GitHub:

1. Open the `Build and Release OnePlus Kernels` workflow.
2. Run workflow with:
   - `op_model`: `OP15`
   - `ksu_options`: `[{"type":"ksun","hash":"dev"}]`
   - `optimize_level`: `O2`
   - `clean_build`: `false` for normal builds, `true` when debugging
   - `make_release`: optional
3. Download the workflow artifact.
4. Treat the resulting image as experimental until it passes RAM boot and flash tests.

Important: the GitHub Actions build can generate a different `Image` hash from the original WildKernels release. Do not assume it is equivalent to the known-working OP-WILD image.

## Safe Test Order

1. Keep a stock/current `boot.img` backup.
2. Test a generated boot image with `fastboot boot` first.
3. Only flash AnyKernel permanently after RAM boot is confirmed.
4. Install the Droidspaces module through KernelSU.
5. Reboot and verify daemon/container startup.
