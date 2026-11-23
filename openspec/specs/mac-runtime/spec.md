# mac-runtime Specification

## Purpose

Defines how eval-coach behaves once it is running on macOS: the AI window, stopping what it started, the setup checks and installs, and which Macs are supported, so a Mac participant can finish the whole series.

## Requirements

### Requirement: Supported Macs
eval-coach SHALL run on macOS 13 or later, on Apple Silicon and on Intel. On a Mac, every Part and the Script track SHALL work as they do on Windows. The promptfoo track needs a Node.js build that requires macOS 13.5 or later; on an older macOS the app SHALL say so in plain words where the promptfoo track is chosen and on the Node.js page, and SHALL offer the Script track, without blocking anything else. Source: GitHub issue #7, open question 1.

#### Scenario: Apple Silicon and Intel
- **WHEN** a participant on either chip completes setup with the Script track
- **THEN** every setup check, the AI window and the course steps behave as on Windows

#### Scenario: promptfoo on macOS 13.0 to 13.4
- **GIVEN** the Mac runs macOS 13.0 up to 13.4
- **WHEN** the participant reaches the track choice or the Node.js page
- **THEN** the text says the promptfoo track needs macOS 13.5 or later and suggests the Script track
- **AND** nothing is downloaded for Node.js

### Requirement: The AI window works on a Mac
The AI window SHALL run the participant's AI in a real pseudo-terminal on macOS, with the same behavior the participant sees on Windows: output appears as it is produced, typing and paste reach the AI, the window can be resized, and a program that exits shows its exit code. The AI SHALL be started in its own process group so the app can stop it and everything it started. The app SHALL keep answering no prompt for the participant and SHALL NOT read terminal text to decide anything (AGENTS.md rules 2 and 3).

#### Scenario: Interactive AI
- **GIVEN** a participant on a Mac starts their AI in the AI window
- **WHEN** they type, paste and resize the window
- **THEN** the AI receives the input and redraws to the new size

#### Scenario: The AI exits
- **WHEN** the AI process ends
- **THEN** the window shows that it ended and its exit code, as on Windows

#### Scenario: AI needing a terminal name
- **GIVEN** an AI that warns about an unknown terminal unless one is named
- **WHEN** it starts on a Mac
- **THEN** it is started with a terminal name it knows, only for the tools listed for that purpose in the content files

### Requirement: New chat and Quit stop everything the app started
On a Mac, "Open a new AI chat", "Start again", closing the app and Quit SHALL end the AI process and every process it started, and SHALL leave none running. Only one AI process runs at a time (AGENTS.md rule 4). If a process ignores a polite stop, the app SHALL force it to end after a short wait.

#### Scenario: New chat
- **GIVEN** an AI is running with a child process
- **WHEN** the participant starts a new chat
- **THEN** both the AI and its child end before the new one starts

#### Scenario: Quit
- **WHEN** the participant presses Quit
- **THEN** the AI window process tree, any quiet background test and any install the app started are ended
- **AND** the Terminal window that started the launcher can be closed without a warning about running processes

#### Scenario: A process ignores the stop
- **GIVEN** the AI does not end after a polite stop
- **WHEN** the short wait passes
- **THEN** it is ended by force

### Requirement: Setup checks and installs use Mac commands on a Mac
On a Mac the setup checks SHALL look for Python, Node.js and promptfoo and the three AIs the way they are installed on a Mac, and every download or install the app offers SHALL use a Mac command and a Mac file. The private Node.js for the promptfoo track SHALL be the pinned build for the chip (Apple Silicon or Intel) and SHALL be accepted only if its SHA-256 equals the built-in value for that chip. Downloads SHALL come only from the hosts AGENTS.md rule 5 lists and SHALL start only after consent. Nothing SHALL need administrator rights or change the computer outside the app's own folders and what the AI's own installer does.

#### Scenario: Node.js for the promptfoo track
- **GIVEN** a Mac on macOS 13.5 or later and the promptfoo track
- **WHEN** the participant agrees to the Node.js install
- **THEN** the build for this chip is downloaded, checked against its fingerprint, unpacked, run once, and put in place under the app's own folder

#### Scenario: Wrong fingerprint
- **WHEN** a downloaded file does not match its built-in fingerprint
- **THEN** it is deleted, nothing is installed, and the page says the file failed its safety check

#### Scenario: Python page
- **GIVEN** the app is running on a Mac
- **WHEN** the Python page shows the Python in use
- **THEN** it shows the Mac Python path and says to start eval-coach again if it cannot be run

### Requirement: A newly installed AI is found without restarting the app
On a Mac, after an AI is installed (by the app's install option or by the participant), the checks SHALL find it in the places Mac installers use (the user's `~/.local/bin`, Homebrew's folders and the AI's own folder) even when the running app was started before the install changed the shell's PATH. The check SHALL only resolve a command and SHALL NOT start the AI or read terminal text (AGENTS.md rule 3).

#### Scenario: Installed a minute ago
- **GIVEN** the participant installed Claude Code while the app was open
- **WHEN** the participant presses "Check everything"
- **THEN** Claude Code is found and offered

#### Scenario: Not installed
- **GIVEN** none of the three AIs is installed
- **WHEN** the checks run
- **THEN** the page offers the Mac install option for each, with its size and a "Show the command" link, as on Windows

### Requirement: The quiet background AI test works on a Mac
Choosing an AI on a Mac SHALL start the same quiet test described in `ai-selection`, with no window and no input, decided only from the process's exit status, ended by its time limit, and stopped (with its children) when cancelled or when another AI process starts.

#### Scenario: Passes
- **GIVEN** a signed-in AI on a Mac
- **WHEN** the participant presses "Use this AI"
- **THEN** the test passes by exit status and the wizard moves on

#### Scenario: Time limit
- **GIVEN** the AI does not finish in its time limit
- **WHEN** the limit is reached
- **THEN** the AI and its children are ended and the wizard moves to the AI working test page, with no failure recorded

### Requirement: Files and folders behave the same on a Mac
The app's folders SHALL be `~/.eval-coach` and `~/eval-project` by default, paths SHALL work with spaces and non-ASCII characters, a project inside a cloud-synced folder that the app already refuses (OneDrive) SHALL still be refused, and no participant file SHALL be overwritten or removed.

#### Scenario: Default folders
- **WHEN** a participant on a Mac accepts the default folders
- **THEN** the project is created under their home folder and nothing existing is overwritten

#### Scenario: Reset on a Mac
- **WHEN** the participant uses either reset in Settings
- **THEN** one backup folder is made under `~/.eval-coach/reset-backup/` before anything is cleared, as on Windows
