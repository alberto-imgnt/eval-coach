# mac-launcher Specification

## Purpose

Lets a participant on a Mac start eval-coach by opening one file, with Python found or installed for them on the way, the same way `single-file-launcher` does on Windows.

## Requirements

### Requirement: One file starts the app on a Mac
Everything a participant needs to start eval-coach on macOS SHALL be in one file, `eval-coach.command`, delivered inside `eval-coach-mac.zip`. Double-clicking it SHALL check for Python, then start the app and open it in the browser, with no other file beside it and no earlier step. Source: GitHub issue #7, mirroring `single-file-launcher`.

#### Scenario: Python is already installed
- **GIVEN** the participant has a working Python 3.9 or later
- **WHEN** the participant double-clicks `eval-coach.command` after unzipping
- **THEN** the app starts and opens in the browser
- **AND** the participant is not asked a question

#### Scenario: The file is alone in its folder
- **GIVEN** `eval-coach.command` is the only file in its folder
- **WHEN** the participant double-clicks it
- **THEN** the app starts

#### Scenario: Opens without being made executable by hand
- **GIVEN** the participant downloaded the zip in a browser and unzipped it by double-clicking
- **WHEN** the participant double-clicks `eval-coach.command`
- **THEN** it opens in Terminal and runs, with no `chmod` step

### Requirement: Gatekeeper and the fallback are explained before they are needed
The setup instructions for the Mac download (`docs/SETUP.md` and the text that accompanies the zip where it is shared) SHALL say, in plain words, that macOS may refuse the first open because the file is not from the App Store, and how to allow it once (right-click the file and choose Open; on macOS 15 and later, Open Anyway in System Settings under Privacy & Security). They SHALL also give a single line to paste into Terminal that starts the launcher without a double-click. They SHALL NOT tell the participant to turn off Gatekeeper or any other protection.

#### Scenario: First open is refused
- **GIVEN** macOS refuses the double-click because the file is from an unidentified developer
- **WHEN** the participant reads the instructions
- **THEN** they find the right-click Open step and the System Settings route, in that order

#### Scenario: Terminal fallback
- **GIVEN** the double-click does not work
- **WHEN** the participant pastes the fallback line into Terminal
- **THEN** the launcher runs exactly as it does from a double-click

#### Scenario: No protection is turned off
- **WHEN** the content tests scan the Mac instructions
- **THEN** none says to disable Gatekeeper, run `sudo`, or use `xattr -c` on a system file

### Requirement: Python is found without asking when it exists
The Mac launcher SHALL look first for a working Python 3.9 or later on the computer (the Python on the participant's PATH, then the usual python.org and Homebrew locations), then in the private copy from an earlier run, and SHALL ask a question only when neither is found. It SHALL NOT run Apple's `/usr/bin/python3` unless the Command Line Tools are already installed, because running it otherwise opens Apple's installer. A candidate SHALL count only when it exits successfully, prints a per-run token and reports a version of 3.9 or later. The launcher SHALL start the app with the interpreter path the candidate reports for itself, not with the candidate's own path, so a shim that picks a Python by folder cannot start a different one. Apple's `/usr/bin/python3` SHALL be recognised by file identity, so a link to it is the same stub, and SHALL never be run without the Command Line Tools on any discovery path.

#### Scenario: Python on the computer
- **GIVEN** a working Python 3.9 or later is installed
- **WHEN** the launcher runs
- **THEN** that Python starts the app and no download is offered

#### Scenario: A shim picks the Python
- **GIVEN** the first `python3` found is a shim that chooses its Python by folder
- **WHEN** the launcher tests it and then starts the app
- **THEN** the app starts with the Python the shim reported for itself

#### Scenario: Apple's stub is never opened
- **GIVEN** the Command Line Tools are not installed and no other Python is found
- **WHEN** the launcher runs
- **THEN** Apple's installer dialog does not open, even when a link in another folder points to the stub
- **AND** the launcher offers the private copy
#### Scenario: Private copy from an earlier run
- **GIVEN** no other Python is found and the private copy from an earlier run works
- **WHEN** the launcher runs
- **THEN** the private copy starts the app and no download is offered

### Requirement: A private Python is installed only after consent
When no working Python is found, the Mac launcher SHALL say what it would install, where, its download and installed size, the download address, and the free disk space, and SHALL say that no administrator rights are needed and nothing else on the computer changes. It SHALL download only after the participant answers yes. An unclear answer SHALL be asked again, up to three times in all, and no answer at all or "no" SHALL count as declining. Source: AGENTS.md rule 5, as amended by this change.

#### Scenario: Consent shown before anything downloads
- **GIVEN** no working Python is found
- **WHEN** the launcher reaches the install question
- **THEN** it shows what, size, where, address and free space
- **AND** nothing has been downloaded yet

#### Scenario: Participant agrees
- **WHEN** the participant types Y
- **THEN** the Python for this Mac's chip is downloaded, checked, unpacked and tried before it is put in place
- **AND** the app then starts with it

#### Scenario: Participant declines
- **WHEN** the participant types N, or gives no answer
- **THEN** nothing is installed and nothing on the computer changes
- **AND** the launcher says what to do next, either start it again and answer Y or install Python from python.org or the company's software portal

#### Scenario: Two windows at once
- **GIVEN** a second launcher window agrees to the install while the first is installing
- **WHEN** the second window reaches the download
- **THEN** it waits for the first to finish and then uses the copy the first installed, without downloading or replacing anything
- **AND** a wait ends if the window holding the lock is gone

### Requirement: The download must match its fixed fingerprint for this chip
The Mac launcher SHALL pick the download for the chip it runs on (Apple Silicon or Intel) and SHALL accept the file only if its SHA-256 fingerprint equals the value built into the launcher for that chip. A mismatch, or a download that cannot be checked, SHALL delete the file, install nothing, and say so. No setting or environment value SHALL change the fingerprint that is required. A Mac running the launcher under Rosetta SHALL get the build that matches the chip the Python will run on.

#### Scenario: Apple Silicon and Intel
- **WHEN** the launcher runs on an Apple Silicon Mac and then on an Intel Mac
- **THEN** each downloads its own build and checks it against its own fingerprint

#### Scenario: Damaged or altered download
- **WHEN** the downloaded file's fingerprint does not match
- **THEN** the file is deleted and nothing is installed
- **AND** the message says the file failed its safety check and what to do next

#### Scenario: No way to skip the check
- **GIVEN** a participant or program sets an environment value naming a different fingerprint
- **WHEN** the launcher checks a download
- **THEN** the built-in fingerprint is still the one required

### Requirement: Every Mac failure says what happened and what to do next
Every failure the Mac launcher can report (blocked download, timeout, damaged download, unreadable archive, file removed by security software, low disk space, a Python copy in use, missing system tools, an unsupported macOS version, the app stopping with an error) SHALL say in plain words what happened and give a next action that is not "contact someone". After a failure or a decline the Terminal window SHALL stay open until a key is pressed, and an app error SHALL show its exit code.

#### Scenario: Blocked download
- **WHEN** the Python download fails because the network or a proxy blocks it
- **THEN** the message says nothing was installed
- **AND** it tells the participant to check the connection and start it again, or install Python from python.org or the company's software portal

#### Scenario: macOS older than 13
- **GIVEN** the Mac runs a macOS version older than 13
- **WHEN** the launcher runs
- **THEN** it says in plain words that this version of macOS is not supported and which versions are
- **AND** nothing is downloaded

#### Scenario: Window stays open after a failure
- **WHEN** any failure message is shown
- **THEN** the window waits for a key press before closing

#### Scenario: App stops with an error
- **WHEN** the app exits with a non-zero code
- **THEN** the launcher shows that code
- **AND** it says to close the window and start eval-coach again

### Requirement: The Mac launcher works wherever the file is
The Mac launcher SHALL work when the folder holding the file, or the participant's home folder, has spaces, quotes, ampersands, parentheses or exclamation marks in its path, and when the file is run from a folder that is read-only.

#### Scenario: Unusual folder name
- **GIVEN** the file is in a folder named `My Files & (Old)!`
- **WHEN** the participant double-clicks it
- **THEN** the app starts

### Requirement: Replacing the file updates the app on a Mac
Replacing `eval-coach.command` with a newer one SHALL be the whole update: the new file SHALL start the newer app, and the private Python and the participant's saved progress and files SHALL be left as they are.

#### Scenario: Newer file, same computer
- **GIVEN** the participant has run an earlier `eval-coach.command` and has progress saved
- **WHEN** they replace it with a newer one and double-click it
- **THEN** the newer app starts and the saved progress is still there

### Requirement: The Mac download is built, checked and kept in step with Windows
The build SHALL produce `eval-coach.command` and `eval-coach-mac.zip` together with the Windows file, and its smoke check SHALL start the app from each launcher. The zip SHALL keep the executable bit on `eval-coach.command`. The launcher's pinned values SHALL come from one manifest that also lists the Mac Node pins.

#### Scenario: Build output
- **WHEN** the build runs
- **THEN** `dist/eval-coach.cmd`, `dist/eval-coach.command` and `dist/eval-coach-mac.zip` exist

#### Scenario: Executable bit survives
- **WHEN** the zip is unpacked by the system unzip tool
- **THEN** `eval-coach.command` is executable
