start:
	@./makefile_scripts/start.sh $(TOKEN)

stop:
	@./makefile_scripts/stop.sh

build:
	@./makefile_scripts/build.sh

restart:
	@./makefile_scripts/stop.sh & ./makefile_scripts/start.sh $(TOKEN)