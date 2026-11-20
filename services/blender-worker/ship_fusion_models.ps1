# Fusion에서 내보낸 부품 STL(data/fusion/<SKU>) → 웹 glb + 썸네일 → 모델 테스트
#   .\services\blender-worker\ship_fusion_models.ps1 -Skus G646GBB031,G646MEE021
# Blender 경로가 다르면 -Blender 로 넘긴다. 경로는 모두 절대경로로 넘겨야 썸네일이 엉뚱한 곳(C:\apps)에 안 생긴다.
param(
  [Parameter(Mandatory = $true)][string[]]$Skus,
  [string]$Blender = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
)
$ErrorActionPreference = "Continue"
$repo = (Resolve-Path "$PSScriptRoot\..\..").Path
$bpy = "$repo\services\blender-worker\worker\bpy_scripts"
Set-Location $repo
foreach ($s in $Skus) {
  & $Blender -b -P "$bpy\fusion_to_glb.py" -- --sku $s --catalog "$repo\data\catalog\products.json" --src "$repo\data\fusion\$s" --out "$repo\apps\web\models\products" 2>&1 | Select-String "^$s|Error|Traceback"
  & $Blender -b -P "$bpy\render_thumbs.py" -- --models "$repo\apps\web\models\products" --out "$repo\apps\web\img\products" --sku $s 2>&1 | Select-String "Error|Traceback"
}
uv run pytest tests/integration/test_product_models.py -q 2>&1 | Select-Object -Last 2
