$ErrorActionPreference = 'Stop'

$baseDir = 'D:\capstone_radar\ti_toolbox\radar-tracking-system\radar-tracking-system\docs\presentation'
$outPath = Join-Path $baseDir 'radar_modification_story_2026-03-22_final.pptx'
$previewDir = Join-Path $baseDir 'radar_modification_story_preview_final'

function New-Rgb([int]$r, [int]$g, [int]$b) {
    return $r + (256 * $g) + (65536 * $b)
}

function Set-SlideBackground($slide, [int]$color) {
    $slide.FollowMasterBackground = 0
    $slide.Background.Fill.Visible = -1
    $slide.Background.Fill.Solid()
    $slide.Background.Fill.ForeColor.RGB = $color
}

function Add-Rect($slide, [double]$left, [double]$top, [double]$width, [double]$height, [int]$fillColor, [int]$lineColor, [single]$lineWeight = 1.1) {
    $shape = $slide.Shapes.AddShape(1, $left, $top, $width, $height)
    $shape.Fill.Visible = -1
    $shape.Fill.Solid()
    $shape.Fill.ForeColor.RGB = $fillColor
    $shape.Line.Visible = -1
    $shape.Line.ForeColor.RGB = $lineColor
    $shape.Line.Weight = $lineWeight
    return $shape
}

function Add-Text($slide, [double]$left, [double]$top, [double]$width, [double]$height, [string]$text, [int]$fontSize = 20, [int]$fontColor = 0, [bool]$bold = $false, [string]$fontName = 'Malgun Gothic') {
    $tb = $slide.Shapes.AddTextbox(1, $left, $top, $width, $height)
    $tb.TextFrame.TextRange.Text = $text
    $tb.TextFrame.TextRange.Font.Name = $fontName
    $tb.TextFrame.TextRange.Font.NameFarEast = $fontName
    $tb.TextFrame.TextRange.Font.Size = $fontSize
    $tb.TextFrame.TextRange.Font.Bold = [int]$bold
    $tb.TextFrame.TextRange.Font.Color.RGB = $fontColor
    $tb.TextFrame.WordWrap = -1
    $tb.TextFrame.AutoSize = 0
    $tb.TextFrame.MarginLeft = 10
    $tb.TextFrame.MarginRight = 10
    $tb.TextFrame.MarginTop = 8
    $tb.TextFrame.MarginBottom = 8
    $tb.Line.Visible = 0
    $tb.Fill.Visible = 0
    return $tb
}

function Add-Bullets($slide, [double]$left, [double]$top, [double]$width, [double]$height, [string[]]$lines, [int]$fontSize = 18, [int]$fontColor = 0) {
    $bullet = [char]0x2022
    $text = ($lines | ForEach-Object { "$bullet $_" }) -join "`r`n`r`n"
    Add-Text $slide $left $top $width $height $text $fontSize $fontColor $false | Out-Null
}

function Add-Header($slide, [string]$title, [string]$subtitle = '') {
    $navy = New-Rgb 19 41 75
    $gold = New-Rgb 230 172 60
    $white = New-Rgb 255 255 255
    $muted = New-Rgb 214 223 238
    Add-Rect $slide 0 0 960 88 $navy $navy 0 | Out-Null
    Add-Rect $slide 36 76 170 4 $gold $gold 0 | Out-Null
    Add-Text $slide 36 20 620 34 $title 28 $white $true | Out-Null
    if ($subtitle -ne '') {
        Add-Text $slide 36 52 760 18 $subtitle 11 $muted $false | Out-Null
    }
}

function Add-CardTitle($slide, [double]$left, [double]$top, [double]$width, [string]$title, [int]$color) {
    Add-Text $slide $left $top $width 24 $title 20 $color $true | Out-Null
}

$bg = New-Rgb 246 248 251
$navy = New-Rgb 19 41 75
$blue = New-Rgb 44 111 187
$sky = New-Rgb 233 241 252
$mint = New-Rgb 232 245 240
$amber = New-Rgb 255 246 226
$rose = New-Rgb 251 236 233
$line = New-Rgb 210 218 228
$dark = New-Rgb 33 39 48
$gray = New-Rgb 108 119 134
$green = New-Rgb 43 111 86
$red = New-Rgb 166 67 53
$white = New-Rgb 255 255 255

$slides = @(
    [pscustomobject]@{
        Title = 'Radar Tracking System'
        Subtitle = '라이브러리 도입 이후 왜 수정이 계속 필요했는가'
        Build = {
            param($slide)
            Add-Rect $slide 48 124 864 108 $white $line 1 | Out-Null
            Add-Text $slide 70 146 820 34 '한 줄 요약' 20 $navy $true | Out-Null
            Add-Text $slide 70 176 820 42 '알고리즘을 붙인 뒤부터가 오히려 진짜 작업이었다. 문제를 보이게 하고, 화면과 실제 런타임을 맞추고, 설치 자세와 성능 병목을 분리하는 과정이 계속 이어졌다.' 21 $dark $true | Out-Null

            Add-Rect $slide 48 270 270 188 $sky $blue 1.2 | Out-Null
            Add-CardTitle $slide 64 286 236 '출발점' $navy
            Add-Bullets $slide 62 322 242 116 @(
                'TLV Parse, Filter, DBSCAN, Kalman, Viewer 구성',
                'scikit-learn, FilterPy, TI parsing 아이디어 활용',
                '초기 목표는 빠른 동작 확인'
            ) 15 $dark

            Add-Rect $slide 344 270 270 188 $rose $line 1.2 | Out-Null
            Add-CardTitle $slide 360 286 236 '바로 드러난 문제' $navy
            Add-Bullets $slide 358 322 242 116 @(
                'parser validity 불안정',
                'viewer를 그대로 믿기 어려움',
                '실내 clutter와 설치 자세 영향'
            ) 16 $dark

            Add-Rect $slide 640 270 272 188 $mint $line 1.2 | Out-Null
            Add-CardTitle $slide 656 286 238 '발표 핵심' $navy
            Add-Bullets $slide 654 322 244 116 @(
                '라이브러리는 알고리즘 블록만 제공',
                '실제 장비에서는 시스템 정합성이 먼저 중요',
                '그래서 수정이 반복되었다'
            ) 15 $dark
        }
    },
    [pscustomobject]@{
        Title = '왜 수정이 반복되었나'
        Subtitle = '문제는 한 군데가 아니라 네 축에서 동시에 나왔다'
        Build = {
            param($slide)
            $items = @(
                @{L=52; T=132; Fill=$sky; Title='환경 재현성'; Body='requirements, import, cfg 응답이 정리되지 않으면 팀원 PC에서 같은 문제가 재현되지 않았다.'},
                @{L=496; T=132; Fill=$rose; Title='Parser validity'; Body='malformed frame, resync, dropped frame을 분리해 보지 않으면 잘못된 point도 정상처럼 보였다.'},
                @{L=52; T=316; Fill=$mint; Title='Viewer 신뢰성'; Body='viewer와 runtime이 같은 계산 경로를 타지 않으면 화면을 기준으로 잘못 튜닝하게 된다.'},
                @{L=496; T=316; Fill=$amber; Title='실내 설치 조건'; Body='yaw, pitch, height, range gate, clutter가 continuity와 split track에 직접 영향을 줬다.'}
            )
            foreach ($i in $items) {
                Add-Rect $slide $i.L $i.T 412 150 $i.Fill $line 1.2 | Out-Null
                Add-CardTitle $slide ($i.L + 16) ($i.T + 16) 380 $i.Title $navy
                Add-Text $slide ($i.L + 16) ($i.T + 52) 380 72 $i.Body 16 $dark $false | Out-Null
            }
            Add-Text $slide 56 500 844 32 '정리: 수정은 “코드가 틀려서”가 아니라, 라이브러리 위에 실제 장비용 관측 체계와 운영 구조를 올리는 과정이었다.' 18 $navy $true | Out-Null
        }
    },
    [pscustomobject]@{
        Title = '수정 흐름 타임라인'
        Subtitle = '03-15 -> 03-19로 갈수록 알고리즘보다 구조와 검증 체계 쪽으로 이동했다'
        Build = {
            param($slide)
            Add-Rect $slide 90 258 780 6 $navy $navy 0 | Out-Null
            $steps = @(
                @{X=100; Date='03-15'; Head='관측 가능성 확보'; Body='requirements 정리\ncfg 응답 로그\nType1 누락 fail'},
                @{X=260; Date='03-18 초반'; Head='필터 튜닝'; Body='keepout 조정\nmax_range\nz gate'},
                @{X=420; Date='03-18 오후'; Head='구조 분리'; Body='runtime_pipeline 분리\n공용 params'},
                @{X=580; Date='03-18 밤'; Head='viewer 정렬'; Body='shared path\ncallback renderer'},
                @{X=740; Date='03-19'; Head='좌표/성능 분리'; Body='yaw/pitch/height\nworker/draw 분리'}
            )
            foreach ($s in $steps) {
                Add-Rect $slide $s.X 242 20 36 $navy $navy 0 | Out-Null
                Add-Text $slide ($s.X - 10) 208 84 24 $s.Date 16 $navy $true | Out-Null
                Add-Rect $slide ($s.X - 48) 300 116 126 $white $line 1.1 | Out-Null
                Add-Text $slide ($s.X - 38) 314 96 26 $s.Head 15 $navy $true | Out-Null
                Add-Text $slide ($s.X - 38) 344 96 56 $s.Body 12 $dark $false | Out-Null
            }
            Add-Text $slide 56 478 840 44 '핵심 변화: “알고리즘이 있냐”에서 끝나지 않고, runtime 구조 정합성, 시각화 신뢰성, 설치 좌표 보정, 자동 리포트까지 확장됐다.' 18 $navy $true | Out-Null
        }
    },
    [pscustomobject]@{
        Title = '무엇을 어떻게 고쳤나'
        Subtitle = '변경은 크게 세 단계로 설명하는 것이 발표에 가장 안정적이다'
        Build = {
            param($slide)
            Add-Rect $slide 48 140 270 300 $sky $blue 1.2 | Out-Null
            Add-CardTitle $slide 64 158 236 '1. 실패를 보이게 함' $navy
            Add-Bullets $slide 62 198 242 210 @(
                'cfg 응답 로그 추가',
                'Type1 누락 frame fail',
                'error log / correction report 누적',
                '문제를 재현 가능한 상태로 전환'
            ) 16 $dark

            Add-Rect $slide 344 140 270 300 $mint $line 1.2 | Out-Null
            Add-CardTitle $slide 360 158 236 '2. viewer와 runtime 정렬' $navy
            Add-Bullets $slide 358 198 242 210 @(
                'motion cloud / trail / overlay 추가',
                'shared processing path 사용',
                'callback renderer로 재구성',
                '화면과 로그를 같은 근거로 비교'
            ) 16 $dark

            Add-Rect $slide 640 140 272 300 $amber $line 1.2 | Out-Null
            Add-CardTitle $slide 656 158 238 '3. 설치/성능 왜곡 분리' $navy
            Add-Bullets $slide 654 198 244 210 @(
                'sensor yaw / pitch / height 보정',
                'world coordinate 기준 정렬',
                'worker와 draw 분리',
                'logging 병목과 draw 병목 분리 측정'
            ) 16 $dark

            Add-Text $slide 52 474 860 30 '즉, 수정은 기능 추가라기보다 “무엇을 믿어야 하는지”를 만드는 작업이었다.' 18 $navy $true | Out-Null
        }
    },
    [pscustomobject]@{
        Title = '로그로 본 개선 근거'
        Subtitle = '문제가 사라진 것이 아니라, 병목이 점점 더 분리되어 보이게 되었다'
        Build = {
            param($slide)
            Add-Rect $slide 52 138 258 156 $rose $line 1.2 | Out-Null
            Add-CardTitle $slide 68 156 224 '03-15 초기 상태' $navy
            Add-Text $slide 68 198 224 72 "FPS 0.158`r`navg pipe 6311 ms`r`n사실상 unusable" 19 $red $true | Out-Null

            Add-Rect $slide 352 138 258 156 $amber $line 1.2 | Out-Null
            Add-CardTitle $slide 368 156 224 '03-18 중간 상태' $navy
            Add-Text $slide 368 198 224 72 "FPS 9.36`r`nfilter 동작`r`nzero-track 많음" 19 $dark $true | Out-Null

            Add-Rect $slide 652 138 258 156 $mint $line 1.2 | Out-Null
            Add-CardTitle $slide 668 156 224 '03-19 최근 상태' $navy
            Add-Text $slide 668 198 224 72 "FPS 9.87`r`nparser health 개선`r`n실사용 가능성 확인" 19 $green $true | Out-Null

            Add-Rect $slide 52 326 858 170 $white $line 1.2 | Out-Null
            Add-CardTitle $slide 68 344 300 '최근 로그 해석' $navy
            Add-Bullets $slide 66 382 826 92 @(
                '20260319_023912 기준 Avg FPS 9.915, parse_fail 3, resync 25, dropped 5로 health는 확실히 좋아졌다',
                '남은 문제는 zero-track와 multi-track split로, 이제는 range gate / ROI / continuity 최적화 단계다',
                '즉 “전체가 안 됨” 단계는 벗어났고, 남은 병목이 더 구체적으로 보이기 시작했다'
            ) 16 $dark
        }
    },
    [pscustomobject]@{
        Title = '가져온 것과 직접 기여한 것'
        Subtitle = '교수님께는 이 구분을 분명히 보여주는 것이 가장 중요하다'
        Build = {
            param($slide)
            Add-Rect $slide 48 142 286 292 $sky $blue 1.2 | Out-Null
            Add-CardTitle $slide 64 160 252 '가져온 것' $navy
            Add-Bullets $slide 62 200 258 200 @(
                'DBSCAN 알고리즘 구현',
                'Kalman 수학 기반',
                'TI TLV parsing 아이디어',
                '기본 시각화 도구'
            ) 17 $dark

            Add-Rect $slide 356 142 556 292 $mint $line 1.2 | Out-Null
            Add-CardTitle $slide 372 160 522 '직접 기여한 것' $navy
            Add-Bullets $slide 370 200 528 200 @(
                '환경 재현성과 cfg bring-up 체계',
                'parser validity 정책과 health logging',
                'shared runtime pipeline과 공용 params 구조',
                'yaw / pitch / height 기반 world 보정',
                'viewer 구조 재설계와 draw 분리',
                '자동 리포트, 성능 로그, REQ 문서 패키지'
            ) 16 $dark

            Add-Text $slide 52 474 856 32 '발표 결론: 라이브러리를 “붙였다”가 아니라, 그 위에 신뢰 가능한 레이더 SW 운영 구조를 직접 설계했다.' 18 $navy $true | Out-Null
        }
    },
    [pscustomobject]@{
        Title = '현재 상태와 다음 단계'
        Subtitle = '무엇이 해결됐고, 무엇이 앞으로 남았는지'
        Build = {
            param($slide)
            Add-Rect $slide 48 144 404 298 $mint $line 1.2 | Out-Null
            Add-CardTitle $slide 64 162 370 '현재 확보한 것' $navy
            Add-Bullets $slide 62 202 376 206 @(
                'shared runtime pipeline',
                'viewer/runtime truth 정렬',
                'world 보정과 draw 분리',
                '자동 실험 리포트와 요구사항 문서화'
            ) 17 $dark

            Add-Rect $slide 480 144 432 298 $amber $line 1.2 | Out-Null
            Add-CardTitle $slide 496 162 398 '다음 단계' $navy
            Add-Bullets $slide 494 202 404 206 @(
                'health gate: stale / malformed / dropped burst fail-safe',
                'max / p95 latency 등 worst-case 지표 추가',
                'EMPTY_SCENE vs SENSOR_UNHEALTHY 분리',
                'RTOS task / queue / WCET 기준 reference skeleton'
            ) 17 $dark

            Add-Rect $slide 48 464 864 56 $navy $navy 0 | Out-Null
            Add-Text $slide 60 478 840 34 '최종 메시지: 수정이 많았던 이유는 라이브러리가 부족해서가 아니라, 실제 장비에서 믿을 수 있는 시스템으로 바꾸는 과정이었기 때문이다.' 15 $white $true | Out-Null
        }
    }
)

$powerPoint = $null
$presentation = $null
try {
    if (Test-Path $previewDir) {
        Remove-Item $previewDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $previewDir | Out-Null

    $powerPoint = New-Object -ComObject PowerPoint.Application
    $powerPoint.Visible = -1
    $presentation = $powerPoint.Presentations.Add()

    $index = 1
    foreach ($item in $slides) {
        $slide = $presentation.Slides.Add($index, 12)
        Set-SlideBackground $slide $bg
        Add-Header $slide $item.Title $item.Subtitle
        & $item.Build $slide
        Add-Text $slide 36 522 520 12 'Source: docs/experiment_journal.md, docs/performance_log.md, correction report' 9 $gray $false | Out-Null
        Add-Text $slide 896 520 28 12 ("{0}" -f $index) 10 $gray $false | Out-Null
        $index += 1
    }

    if (Test-Path $outPath) {
        Remove-Item $outPath -Force
    }
    $presentation.SaveAs($outPath)
    $presentation.Export($previewDir, 'PNG', 1280, 720)
    $presentation.Close()
    $powerPoint.Quit()
    Write-Output "PPTX_CREATED:$outPath"
    Write-Output "PREVIEW_DIR:$previewDir"
}
catch {
    if ($presentation) {
        try { $presentation.Close() } catch {}
    }
    if ($powerPoint) {
        try { $powerPoint.Quit() } catch {}
    }
    throw
}
