THEOS_PACKAGE_DIR_NAME = debs

PACKAGE_VERSION = $(THEOS_PACKAGE_BASE_VERSION)

DEBUG = 0

INSTALL_TARGET_PROCESSES = SpringBoard

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = NotEnoughIDsPE

NotEnoughIDsPE_FILES = Tweak.xm
NotEnoughIDsPE_FRAMEWORKS = UIKit CoreGraphics
TARGET = iphone:clang:16.5:9.0
NotEnoughIDsPE_CFLAGS = -fobjc-arc
NotEnoughIDsPE_CCFLAGS = -std=c++14 -stdlib=libc++ -fno-rtti -fno-exceptions

ARCHS = arm64

include $(THEOS_MAKE_PATH)/tweak.mk
include $(THEOS)/makefiles/aggregate.mk

after-install::
	install.exec "killall -9 '-'"