# build-merged-bin.ps1
# Build the EWS T-Beam firmware and produce a single merged image + SPIFFS
# that esp-web-tools (index.html + manifest.json) can flash in one shot.
#
# Hasil akhir: webflasher\firmware-merged.bin  (firmware + web UI SPIFFS)
#
# Jalankan dari mana saja:
#   powershell -ExecutionPolicy Bypass -File webflasher\build-merged-bin.ps1
#
# Prasyarat: Python + PlatformIO (script akan install PlatformIO bila belum ada).

$ErrorActionPreference = "Stop"

# --- lokasi ---
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path          # ...\webflasher
$FirmwareDir = Join-Path (Split-Path -Parent $ScriptDir) "firmware"     # ...\firmware
$Env         = "ttgo-t-beam-ews"
$BuildDir    = Join-Path $FirmwareDir ".pio\build\$Env"
$OutBin      = Join-Path $ScriptDir "firmware-merged.bin"

Write-Host "==> Firmware dir : $FirmwareDir"
Write-Host "==> Env          : $Env"

# --- pastikan PlatformIO ada ---
try { python -m platformio --version | Out-Null }
catch {
  Write-Host "==> PlatformIO belum ada, meng-install..."
  python -m pip install --upgrade platformio
}

# --- compile firmware ---
Write-Host "==> Compile firmware (pio run)..."
python -m platformio run -e $Env -d $FirmwareDir

# --- build image SPIFFS (web UI + default config) ---
Write-Host "==> Build SPIFFS image (buildfs)..."
python -m platformio run -e $Env -d $FirmwareDir -t buildfs

# --- cari boot_app0.bin dari framework arduino-esp32 ---
$BootApp0 = Get-ChildItem -Recurse -ErrorAction SilentlyContinue `
  "$env:USERPROFILE\.platformio\packages\framework-arduinoespressif32\tools\partitions\boot_app0.bin" |
  Select-Object -First 1 -ExpandProperty FullName
if (-not $BootApp0) { throw "boot_app0.bin tidak ditemukan. Jalankan 'pio run' dulu agar framework ter-download." }

# --- offset SPIFFS dari partitions_ews.csv (spiffs = 0x3D0000) ---
$SpiffsOffset = "0x3D0000"

Write-Host "==> Merge jadi satu image: $OutBin"
python -m esptool --chip esp32 merge_bin -o $OutBin `
  --flash_mode dio --flash_freq 40m --flash_size 4MB `
  0x1000   "$BuildDir\bootloader.bin" `
  0x8000   "$BuildDir\partitions.bin" `
  0xe000   "$BootApp0" `
  0x10000  "$BuildDir\firmware.bin" `
  $SpiffsOffset "$BuildDir\spiffs.bin"

Write-Host ""
Write-Host "==> SELESAI. File siap flash:" -ForegroundColor Green
Write-Host "    $OutBin"
Write-Host "    Taruh bersama index.html + manifest.json, host via HTTPS (mis. GitHub Pages)."
