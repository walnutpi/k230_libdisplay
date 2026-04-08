# Makefile for display library
# Based on the original CMakeLists.txt from buildroot

CC = gcc
CXX = g++
AR = ar

# Compiler flags
CFLAGS = -Wall -Wextra -fPIC -std=c11 -D_GNU_SOURCE
CXXFLAGS = -Wall -Wextra -fPIC -std=c++17 -D_GNU_SOURCE

# Installation directories
PREFIX ?= /usr/local
INCLUDEDIR = $(PREFIX)/include
LIBDIR = $(PREFIX)/lib
PKGCONFIGDIR = $(LIBDIR)/pkgconfig

# Project info
PROJECT_NAME = display
PROJECT_VERSION = 1.0
PROJECT_DESCRIPTION = "abstruct to libdrm"

# Source files
LIB_SOURCES = src/display.c
TEST_SOURCES = src/test.cpp

# Object files
LIB_OBJECTS = $(LIB_SOURCES:.c=.o)
TEST_OBJECTS = $(TEST_SOURCES:.cpp=.o)

# Library output
LIBRARY = lib$(PROJECT_NAME).so
TEST_BINARY = test-$(PROJECT_NAME)

# pkg-config file
PC_FILE = $(PROJECT_NAME).pc

# Check if we should build tests (default: yes)
BUILD_TEST ?= 1

# libdrm configuration - manually specify paths
LIBDRM_INCLUDE_PATH ?= /usr/include/libdrm
LIBDRM_LIB_PATH ?= /usr/lib
LIBDRM_LIBS = -ldrm

# Include paths
INCLUDES = -Iinclude -I$(LIBDRM_INCLUDE_PATH)

# Default target
all: library $(if $(filter 1,$(BUILD_TEST)),test)

# Build shared library
library: $(LIBRARY)

$(LIBRARY): $(LIB_OBJECTS)
	$(CC) -shared -o $@ $^ $(LIBDRM_LIBS)

# Compile C source files
%.o: %.c
	$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

# Compile C++ source files
%.o: %.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

# Build test executable
test: $(TEST_BINARY)

$(TEST_BINARY): $(TEST_OBJECTS) $(LIBRARY)
	$(CXX) $(CXXFLAGS) $^ -o $@ -L. -L$(LIBDRM_LIB_PATH) -l$(PROJECT_NAME) $(LIBDRM_LIBS) -Wl,-rpath,.

# Install targets
install: all
	# Create installation directories
	mkdir -p $(DESTDIR)$(INCLUDEDIR)
	mkdir -p $(DESTDIR)$(LIBDIR)
	mkdir -p $(DESTDIR)$(PKGCONFIGDIR)
	
	# Install headers
	cp -r include/* $(DESTDIR)$(INCLUDEDIR)/
	
	# Install library
	cp $(LIBRARY) $(DESTDIR)$(LIBDIR)/
	
	# Generate and install pkg-config file
	sed \
		-e 's|@CMAKE_INSTALL_PREFIX@|$(PREFIX)|g' \
		-e 's|@PROJECT_NAME@|$(PROJECT_NAME)|g' \
		-e 's|@PROJECT_DESCRIPTION@|$(PROJECT_DESCRIPTION)|g' \
		-e 's|@PROJECT_VERSION@|$(PROJECT_VERSION)|g' \
		display.pc.in > $(DESTDIR)$(PKGCONFIGDIR)/$(PC_FILE)
	
	# Update dynamic linker cache
	if [ -z "$(DESTDIR)" ]; then \
		ldconfig; \
	fi

# Uninstall targets
uninstall:
	rm -f $(DESTDIR)$(INCLUDEDIR)/display.h
	rm -f $(DESTDIR)$(INCLUDEDIR)/pipeline.hpp
	rm -f $(DESTDIR)$(INCLUDEDIR)/thead.h
	rm -f $(DESTDIR)$(LIBDIR)/$(LIBRARY)
	rm -f $(DESTDIR)$(PKGCONFIGDIR)/$(PC_FILE)

# Clean build artifacts
clean:
	rm -f $(LIB_OBJECTS) $(TEST_OBJECTS) $(LIBRARY) $(TEST_BINARY) $(PC_FILE)

# Help target
help:
	@echo "Available targets:"
	@echo "  all       - Build library and test (default)"
	@echo "  library   - Build only the static library"
	@echo "  test      - Build the test executable"
	@echo "  install   - Install library, headers and pkg-config file"
	@echo "  uninstall - Remove installed files"
	@echo "  clean     - Remove build artifacts"
	@echo "  help      - Show this help message"
	@echo ""
	@echo "Variables:"
	@echo "  PREFIX              - Installation prefix (default: /usr/local)"
	@echo "  BUILD_TEST          - Build test programs (0=no, 1=yes, default: 1)"
	@echo "  LIBDRM_INCLUDE_PATH - libdrm include path (default: /usr/include/libdrm)"
	@echo "  LIBDRM_LIB_PATH     - libdrm library path (default: /usr/lib)"
	@echo ""
	@echo "Examples:"
	@echo "  make                                          # Build library and test"
	@echo "  make BUILD_TEST=0                             # Build only library"
	@echo "  make install PREFIX=/opt                      # Install to /opt"
	@echo "  make LIBDRM_INCLUDE_PATH=/custom/include      # Use custom libdrm include path"
	@echo "  make LIBDRM_LIB_PATH=/custom/lib              # Use custom libdrm library path"

.PHONY: all library test install uninstall clean help