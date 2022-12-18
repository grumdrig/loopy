Usage: loo.py OPTS COMMAND [-- WATCH...]
       loo.py OPTS COMMAND [-- WATCH...] ++ OPTS COMMAND [-- WATCH...] ...
       loo.py --for NAME in FILE do OPTS COMMAND [-- WATCH...] ...
       loo.py [-L ARGS]
       loo.py -F LOOPFILE ARGS

Wait for changes to FILEs NAMEd on the command line (except output files), and
run the COMMAND whenever one of them changes.

Multiple such watchlists may be listed in a Loopfile, (or using ++)
implementing as simple build system.

Initial OPTS:
	-q        Print less info
	-v        Print more info
	-f        Faster polling for changes
	-F FNAME  Load the loopfile FNAME
	-L        Load the loopfile `Loopfile`
These options must come first, and apply to all command loops.

Per-command OPTS:
	-#        Run command through head -# (for some integer #)
	-w FNAME  Watch FNAME for changes
	-i FNAME  Ignore changes to FNAME even if appears in COMMAND or WATCH
	-I        Ignore all command line names not explicitly in WATCH
	-o FNAME  Treat FNAME as an output file. Ignore it, and see below.
	-d        'Daemon' mode - start task in background and restart as needed
	-a        Always restart when command quits
	-x        Run command (once) upon startup without waiting for changes
	--for...  Apply command to multiple parameters, explained below

WATCH: Files listed after -- or specified with -w are also watched for
	changes. Although names found in the command are implicitly watched for
	changes IF they are found at startup, explicitly listed files are watched
	whether they exist initially or not.

Filenames regarded as output files or explicitly ignored are not watched for
changes. Output files are those following following a '>' in the command,
preceded in the command with `@`, or listed using the -o flag.

Run-at-startup mode (as otherwise triggered by the -x option) is activated
automatically if any output file is missing at startup. To prevent this
behavior, ignore the file instead (such as with -i).

Multiple command watch loops can be specified by separating them with ++.

Hitting the enter key causes all commands to run (and/or daemons to be
restarted). Or hitting <task number> <enter> will trigger just that command.

LOOPFILES:

Specifying a loopfile with -F causes the options and commands to be read
from lines in the loopfile. Each nonblank line is parsed as if they were
on the command line. Lines beginning with "#" are treated as comments.

Arguments after -F FNAME or -L are passed to the loopfile as $1, $2, etc.
These and other environment variables are substituted in the loopfile.

Running loo.py without any arguments causes it to look for the loopfile
named "Loopfile" in the current directory. The Loopfile contains command line
arguments that would otherwise be passed to loo.py.

Command loops can be duplicated for multiple files with `--for`. The
pattern is `--for VAR in ARG1 ARG2 ... do ...`. In the command, $VAR will
be replaced with each ARG in turn.

EXAMPLES:
	loo.py gcc test.c
		Recompile test.c whenever it changes

	loo.py a.out
		Run a.out whenever it changes

	loo.py gcc test.c ++ a.out
		Do both

	loo.py make test -- *.c *.h
		Run `make test` whenever a .c or .h file changes

	loo.py sed s/day/night/ \< dayfile \> nightfile
		Run sed whenever dayfile changes to produce nightfile. Note that
		the io redirection operators must be escaped. Also note that
		though nightfile is mentioned in the command, it's after a '>'
		and therefore not watched.

	loo.py swiftc -emit-library helper.swift ++ swiftc -lhelper program.swift -- libhelper.dylib ++ ./program
		Recompile the library "helper" when "helper.swift" changes. And:
		Recompile "program" when program.swift or the library changes. And:
		Run the program whenever it is regenerated.

	loo.py --for FILE in *.c do cc -o $FILE
		Set watches to compile any C file that changes

