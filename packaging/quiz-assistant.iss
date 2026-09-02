#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\artifacts\onedir\quiz-assistant"
#endif

#define AppName "Quiz Assistant"
#define AppPublisher "Quiz Assistant"
#define AppExeName "quiz-assistant.exe"

[Setup]
AppId={{C4D6A0A7-9C52-4BD3-9A5E-4BB9A6C1A6D7}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\QuizAssistant
DefaultGroupName={#AppName}
OutputBaseFilename=QuizAssistant-{#AppVersion}-setup
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
ChangesAssociations=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[CustomMessages]
chinesesimplified.TesseractWarning=未检测到 Tesseract OCR。截图识别功能需要单独安装 Tesseract；现在打开安装说明吗？
english.TesseractWarning=Tesseract OCR was not detected. Screenshot recognition requires a separate Tesseract installation. Open the installation guide now?

[Code]
function TesseractPath(): String;
var
  Candidate: String;
begin
  Candidate := GetEnv('TESSERACT_CMD');
  if (Candidate <> '') and FileExists(Candidate) then
  begin
    Result := Candidate;
    exit;
  end;

  Candidate := ExpandConstant('{autopf}\Tesseract-OCR\tesseract.exe');
  if FileExists(Candidate) then
  begin
    Result := Candidate;
    exit;
  end;
  Candidate := ExpandConstant('{autopf32}\Tesseract-OCR\tesseract.exe');
  if FileExists(Candidate) then
  begin
    Result := Candidate;
    exit;
  end;
  Candidate := ExpandConstant('{localappdata}\Programs\Tesseract-OCR\tesseract.exe');
  if FileExists(Candidate) then
  begin
    Result := Candidate;
    exit;
  end;
  Result := '';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ErrorCode: Integer;
begin
  Result := True;
  if (CurPageID = wpReady) and (TesseractPath() = '') then
  begin
    if MsgBox(ExpandConstant('{cm:TesseractWarning}'), mbInformation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://github.com/UB-Mannheim/tesseract/wiki', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
  end;
end;
