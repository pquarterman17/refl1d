;-------------------------------------------------------------------------------
; Includes
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "WinVer.nsh"
!include "x64.nsh"

;-------------------------------------------------------------------------------
; Constants
!ifndef PRODUCT_NAME
    !define PRODUCT_NAME "Refl1D"
!endif
!define /date CurrentYear "%Y"
!define PRODUCT_DESCRIPTION "Refl1D reflectometry fitting package"
!define COPYRIGHT "Copyright ${CurrentYear} The Refl1D developers"
!ifndef PRODUCT_VERSION
    !define PRODUCT_VERSION "1.0.0.0"
!endif
!define SETUP_VERSION 1.0.0.0
!ifndef SRC
    !define SRC "..\conda_packed"
!endif

;-------------------------------------------------------------------------------
; Attributes
Name "${PRODUCT_NAME}"
OutFile "Refl1DWebviewSetup.exe"
InstallDir "$LocalAppData\${PRODUCT_NAME}"
InstallDirRegKey HKCU "Software\Reflectometry-Org\${PRODUCT_NAME}" ""
RequestExecutionLevel user ; user|highest|admin

;-------------------------------------------------------------------------------
; Version Info
VIProductVersion "${PRODUCT_VERSION}"
VIAddVersionKey "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey "ProductVersion" "${PRODUCT_VERSION}"
VIAddVersionKey "FileDescription" "${PRODUCT_DESCRIPTION}"
VIAddVersionKey "LegalCopyright" "${COPYRIGHT}"
VIAddVersionKey "FileVersion" "${SETUP_VERSION}"

;-------------------------------------------------------------------------------
; Modern UI Appearance
!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\orange-install.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "${NSISDIR}\Contrib\Graphics\Header\orange.bmp"
!define MUI_WELCOMEFINISHPAGE_BITMAP "${NSISDIR}\Contrib\Graphics\Wizard\orange.bmp"
!define MUI_FINISHPAGE_NOAUTOCLOSE

;-------------------------------------------------------------------------------
; Installer Pages
!insertmacro MUI_PAGE_WELCOME
;!insertmacro MUI_PAGE_LICENSE "${NSISDIR}\Docs\Modern UI\License.txt"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

;-------------------------------------------------------------------------------
; Uninstaller Pages
!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

;-------------------------------------------------------------------------------
; Languages
!insertmacro MUI_LANGUAGE "English"

;-------------------------------------------------------------------------------
; Installer Sections
Section "Webview Server" SEC01
    SetOutPath "$INSTDIR"
    File /r "${SRC}\*"
    WriteRegStr HKCU "Software\Reflectometry-Org\${PRODUCT_NAME}" "Install_Dir" "$INSTDIR"
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Fork: write a launcher that logs to $INSTDIR\launch.log and PAUSES when
    ; refl1d fails to start, so a broken launch shows the reason instead of a
    ; window that closes instantly. The stock shortcut ran powershell with no
    ; -NoExit, so any error (e.g. an OS policy block on the bundled python.exe)
    ; vanished before it could be read. Routing through cmd avoids PowerShell
    ; execution-policy issues and the .lnk quoting fragility.
    FileOpen $0 "$INSTDIR\refl1d_launch.bat" w
    FileWrite $0 "@echo off$\r$\n"
    FileWrite $0 "setlocal$\r$\n"
    FileWrite $0 "set $\"LOG=%~dp0launch.log$\"$\r$\n"
    FileWrite $0 "echo [%date% %time%] launching refl1d > $\"%LOG%$\"$\r$\n"
    FileWrite $0 "$\"%~dp0python.exe$\" -m refl1d --use-persistent-path 1>>$\"%LOG%$\" 2>&1$\r$\n"
    FileWrite $0 "set $\"RC=%errorlevel%$\"$\r$\n"
    FileWrite $0 "if not $\"%RC%$\"==$\"0$\" ($\r$\n"
    FileWrite $0 "  echo.$\r$\n"
    FileWrite $0 "  echo Refl1D exited with error code %RC%.  Log: $\"%LOG%$\"$\r$\n"
    FileWrite $0 "  echo --------------------------------------------------$\r$\n"
    FileWrite $0 "  type $\"%LOG%$\"$\r$\n"
    FileWrite $0 "  echo --------------------------------------------------$\r$\n"
    FileWrite $0 "  pause$\r$\n"
    FileWrite $0 ")$\r$\n"
    FileWrite $0 "endlocal$\r$\n"
    FileClose $0

    ; Fork: a self-contained diagnostic the user can run on a locked-down
    ; machine (where they can't fetch our diagnostic script). Double-clicking
    ; the "Refl1D Diagnostics" shortcut writes Desktop\refl1d_diag.txt and shows
    ; it on screen. cmd-only (no PowerShell) so it survives script restrictions.
    FileOpen $0 "$INSTDIR\refl1d_diagnose.bat" w
    FileWrite $0 "@echo off$\r$\n"
    FileWrite $0 "setlocal$\r$\n"
    FileWrite $0 "set $\"REPORT=%USERPROFILE%\Desktop\refl1d_diag.txt$\"$\r$\n"
    FileWrite $0 "echo Refl1D self-diagnostic > $\"%REPORT%$\"$\r$\n"
    FileWrite $0 "echo install dir: %~dp0 >> $\"%REPORT%$\"$\r$\n"
    FileWrite $0 "echo. >> $\"%REPORT%$\"$\r$\n"
    FileWrite $0 "echo [1] Can the bundled python run? (expect Python 3.12.x) >> $\"%REPORT%$\"$\r$\n"
    FileWrite $0 "$\"%~dp0python.exe$\" --version >> $\"%REPORT%$\" 2>&1$\r$\n"
    FileWrite $0 "echo. >> $\"%REPORT%$\"$\r$\n"
    FileWrite $0 "echo [2] Which build? (want refl1d 1.0.2+pq4  bumps 1.0.5rc2) >> $\"%REPORT%$\"$\r$\n"
    FileWrite $0 "$\"%~dp0python.exe$\" -c $\"import refl1d,bumps;print('refl1d',refl1d.__version__,'bumps',bumps.__version__)$\" >> $\"%REPORT%$\" 2>&1$\r$\n"
    FileWrite $0 "echo. >> $\"%REPORT%$\"$\r$\n"
    FileWrite $0 "echo [3] Is the CSV export feature present? >> $\"%REPORT%$\"$\r$\n"
    FileWrite $0 "$\"%~dp0python.exe$\" -c $\"import refl1d.webview.server.export_csv as m;print('CSV export present' if hasattr(m,'write_parameters_csv') else 'MISSING')$\" >> $\"%REPORT%$\" 2>&1$\r$\n"
    FileWrite $0 "echo. >> $\"%REPORT%$\"$\r$\n"
    FileWrite $0 "echo [4] Are you a local admin? (any line below = yes) >> $\"%REPORT%$\"$\r$\n"
    FileWrite $0 "whoami /groups | findstr /i $\"S-1-5-32-544$\" >> $\"%REPORT%$\" 2>&1$\r$\n"
    FileWrite $0 "echo. >> $\"%REPORT%$\"$\r$\n"
    FileWrite $0 "echo Done. >> $\"%REPORT%$\"$\r$\n"
    FileWrite $0 "type $\"%REPORT%$\"$\r$\n"
    FileWrite $0 "echo.$\r$\n"
    FileWrite $0 "echo ============================================================$\r$\n"
    FileWrite $0 "echo A copy was saved to your Desktop as  refl1d_diag.txt$\r$\n"
    FileWrite $0 "echo ============================================================$\r$\n"
    FileWrite $0 "pause$\r$\n"
    FileWrite $0 "endlocal$\r$\n"
    FileClose $0

    ; Fork: a plain-text fallback guide in the install folder.
    FileOpen $0 "$INSTDIR\LAUNCH-HELP.txt" w
    FileWrite $0 "Refl1D - how to launch if the icon does not work$\r$\n$\r$\n"
    FileWrite $0 "This build (refl1d 1.0.2+pq4) includes the CSV parameter export.$\r$\n$\r$\n"
    FileWrite $0 "If the desktop / Start Menu icon does nothing or errors, open$\r$\n"
    FileWrite $0 "Command Prompt (cmd.exe) and run this (pure exe, no script layer):$\r$\n$\r$\n"
    FileWrite $0 "    $\"%LOCALAPPDATA%\${PRODUCT_NAME}\python.exe$\" -m refl1d$\r$\n$\r$\n"
    FileWrite $0 "Leave that window open while using Refl1D.$\r$\n$\r$\n"
    FileWrite $0 "Check which build is running:$\r$\n"
    FileWrite $0 "    $\"%LOCALAPPDATA%\${PRODUCT_NAME}\python.exe$\" -m refl1d --where$\r$\n"
    FileWrite $0 "It should say 1.0.2+pq4 (fork build). If it says 1.0.1, that is the$\r$\n"
    FileWrite $0 "old stock version - do NOT just type 'refl1d'.$\r$\n$\r$\n"
    FileWrite $0 "Full self-check: run 'Refl1D Diagnostics' from the Start Menu.$\r$\n"
    FileClose $0

    ; Registry entries
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                     "DisplayName" "${PRODUCT_NAME}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                     "UninstallString" '"$INSTDIR\uninstall.exe"'
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                      "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                      "NoRepair" 1
SectionEnd

Section "Start Menu Shortcuts" SEC02
    CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
    ; Fork: PRIMARY launch targets python.exe DIRECTLY (no powershell/.bat
    ; wrapper). The original went powershell -> -Command -> python.exe; the
    ; outer script layer is exactly what a "running scripts is disabled" /
    ; script-rule policy blocks. A direct exe launch is governed only by exe
    ; rules (which clearly permit per-user installs here, since the install
    ; succeeded), so it has the best chance of launching on a locked machine.
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Refl1DWebview.lnk" \
        "$INSTDIR\python.exe" "-m refl1d --use-persistent-path" \
        "$INSTDIR\share\icons\refl1d.ico"
    ; Secondary: logged launch (writes launch.log, pauses on error) for when the
    ; user needs to SEE why a launch failed. Goes through cmd, not powershell.
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Refl1D (logged launch).lnk" \
        "$INSTDIR\refl1d_launch.bat" "" \
        "$INSTDIR\share\icons\refl1d.ico"
    ; Self-service diagnostic (writes Desktop\refl1d_diag.txt).
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Refl1D Diagnostics.lnk" \
        "$INSTDIR\refl1d_diagnose.bat" "" \
        "$INSTDIR\share\icons\refl1d.ico"
    SetOutPath "%USERPROFILE%"
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Refl1DPowershell.lnk" \
        "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" \
        '-NoExit -NoProfile -Command ""$INSTDIR\Library\bin\micromamba.exe shell hook -s powershell | Out-String | Invoke-Expression ; micromamba activate $INSTDIR""' \
        ""

SectionEnd

Section "Desktop Shortcut" SEC03
    SetShellVarContext current
    ; Fork: direct python.exe launch (see SEC02 rationale).
    CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" \
        "$INSTDIR\python.exe" "-m refl1d --use-persistent-path" \
        "$INSTDIR\share\icons\refl1d.ico"
SectionEnd

Section "CLI Commands" SEC04
    DetailPrint "Setting up console commands..."
    nsExec::Exec '"$INSTDIR\Scripts\conda-unpack.exe"'
    Pop $0
    DetailPrint "Return code: $0"
SectionEnd

;-------------------------------------------------------------------------------
; Uninstaller Sections
Section "Uninstall"
	Delete "$INSTDIR\Uninstall.exe"
    RMDir /r /REBOOTOK "$INSTDIR"
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\*.lnk"
    RMDir  "$SMPROGRAMS\${PRODUCT_NAME}"
	DeleteRegKey /ifempty HKCU "Software\Reflectometry-Org\${PRODUCT_NAME}"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
SectionEnd
