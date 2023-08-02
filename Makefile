configure:
	@./makefile_scripts/configure.sh

start:
	@./makefile_scripts/start.sh $(MODE)

stop:
	@./makefile_scripts/stop.sh

build:
	@./makefile_scripts/build.sh