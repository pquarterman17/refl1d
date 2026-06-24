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
    ; Fork: launch through the logging wrapper (see SEC01) instead of a bare
    ; powershell -Command, so launch failures are visible and logged.
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Refl1DWebview.lnk" \
        "$INSTDIR\refl1d_launch.bat" "" \
        "$INSTDIR\share\icons\refl1d.ico"
    SetOutPath "%USERPROFILE%"
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Refl1DPowershell.lnk" \
        "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" \
        '-NoExit -NoProfile -Command ""$INSTDIR\Library\bin\micromamba.exe shell hook -s powershell | Out-String | Invoke-Expression ; micromamba activate $INSTDIR""' \
        ""

SectionEnd

Section "Desktop Shortcut" SEC03
    SetShellVarContext current
    ; Fork: same logging wrapper as the Start Menu shortcut.
    CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" \
        "$INSTDIR\refl1d_launch.bat" "" \
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
