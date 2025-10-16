# Windows & External API Usage – Phase 1 Map

Data source: `rabin2 -i TotalA.exe` plus call-site inspection during Phase 1.  
This snapshot groups imported functions by library and annotates known call sites or subsystems that rely on them.

## KERNEL32.dll

- **Process & Threading:** `GetVersion`, `GetModuleHandleA`, `CreateThread`, `SetThreadPriority`, `WaitForSingleObject`, `TlsAlloc/TlsSetValue`, `GetCurrentThreadId`.  
  - Used during startup (`entry0`, `fcn.004eb040`) for OS detection and TLS setup; scheduler tuning appears in `fcn.0049e830`.
- **Memory Management:** `HeapCreate/HeapDestroy`, `GlobalAlloc/GlobalLock/GlobalUnlock`, `VirtualAlloc/VirtualFree/VirtualProtect`, `GlobalMemoryStatus`.  
  - Heap bootstrap lives in `fcn.004f1830`; display setup (`fcn.004b5980`) queries `GlobalMemoryStatus`.
- **File & I/O:** `CreateFileA`, `ReadFile`, `WriteFile`, `SetFilePointer`, `GetFileSize`, `FlushFileBuffers`.  
  - Resource managers (`fcn.004916a0`, `fcn.0042f960`) call into these for CD/asset streaming.
- **Time & Profiling:** `QueryPerformanceCounter`, `GetTickCount`, `Sleep`.  
  - `fcn.004b5980` seeds frame timers with `GetTickCount`.
- **Locale & String Utilities:** `CompareStringA/W`, `GetLocaleInfoA/W`, `MultiByteToWideChar`, `EnumSystemLocalesA`.  
  - Leveraged by `fcn.004f1460` when parsing command line and environment blocks.
- **Registry & Profile Access:** `GetPrivateProfileStringA`, `GetPrivateProfileIntA`, `GetVolumeInformationA`.  
  - Ties into configuration readers inside the resource pipeline.

## USER32.dll

- **Window & Message Loop:** `RegisterClassA`, `CreateWindowExA`, `ShowWindow`, `UpdateWindow`, `DestroyWindow`, `GetMessageA`, `TranslateMessage`, `DispatchMessageA`.  
  - Central to `fcn.004b5980` and the main loop inside `fcn.0049e830`.
- **Input Handling:** `GetAsyncKeyState`, `GetKeyState`, `SetCursorPos`, `GetCursorPos`, `RegisterHotKey`.  
  - Polled inside `fcn.004c1b80` and other input helpers.
- **UI Helpers:** `MessageBoxA`, `DialogBoxIndirectParamA`, `SendMessageA`, `SendDlgItemMessageA`, `SetDlgItemTextA`.  
  - Error states (e.g., DirectX failure) display via `MessageBoxA` in `fcn.004b5980`.
- **Clipboard & System Metrics:** `OpenClipboard`, `GetSystemMetrics`, `SystemParametersInfoA`.  
  - Window initialisation uses `SystemParametersInfoA` to adapt to desktop metrics.

## GDI32.dll

- `CreatePalette`, `SelectPalette`, `CreateCompatibleDC`, `CreateDIBSection`, `BitBlt`, `TextOutA`, `DeleteObject`, `DeleteDC`.  
  - `fcn.004b5980` builds the primary rendering surface and cleans up via `DeleteDC`/`DeleteObject`; GDI fallbacks support UI overlays.

## ADVAPI32.dll

- `RegOpenKeyExA`, `RegQueryValueExA`, `RegSetValueExA`, `RegFlushKey`, `RegCloseKey`, `RegCreateKeyExA`, `RegSetValueExA`.  
  - `fcn.0049e830` writes the Audio CD autoplay verb (`"cdshell"`); other init routines persist configuration.

## TDRAW.dll (DirectDraw)

- `DirectDrawCreate`.  
  - Called from `fcn.004b5510` and `fcn.0047bf70` to create the DirectDraw device and query capabilities.

## DSOUND.dll (DirectSound)

- `DirectSoundCreate`.  
  - Wrapped by `fcn.004cef90` during audio subsystem initialisation (`fcn.0049e830` call chain).

## WGMUS.dll (Wave/MCI Helpers)

- `waveOutGetNumDevs`, `waveOutSetVolume`, `PlaySoundA`, `mciSendStringA`, `auxGetDevCapsA`.  
  - Suggests legacy WinMM playback support; invoked by audio mixer routines near `0x4cee50`.

## SHELL32.dll

- `ShellExecuteA`.  
  - Likely used for launching browser/help or replaying CD tracks; not yet exercised in observed flow but listed for future tracing.

## smackw32.DLL / TPLAYX.dll

- Smacker video playback (multiple ordinal imports).  
  - Cinematic subsystem not yet analysed; functions in the `0x4ce***` range reference these ordinals.

## Other Notes

- `OutputDebugStringA` and `DebugBreak` are imported, indicating optional debug logging and assert mechanisms (not triggered in current traces).
- The presence of both ANSI and Unicode variants of locale/environment APIs underlines the game's robust command-line parsing (already mapped in `fcn.004f1460`).
- Network-related imports are absent, implying multiplayer may either be in another module or leverage custom code (to be confirmed in later phases).
