# bugos-shell: de eigen schil van BugOS (zie docs/STANDALONE.md). Wordt gebouwd in de bouwstap van het Containerfile.
cmake_minimum_required(VERSION 3.16)
project(bugos-shell LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 6.4 REQUIRED COMPONENTS Core Gui Qml Quick DBus)

add_executable(bugos-shell
    src/main.cpp
    src/opdracht.cpp
    src/meldingen.cpp
    src/schil.cpp
    src/instellingen.cpp
    src/systeemvak.cpp
    src/osd.cpp
)
target_link_libraries(bugos-shell PRIVATE Qt6::Core Qt6::Gui Qt6::Qml Qt6::Quick Qt6::DBus)

# layer-shell-qt (van KDE, in Kinoite): de taakbalk onderaan met gereserveerde ruimte, menu's erboven. Zonder (een
# test op een andere computer) bouwt de schil ook, met gewone vensters.
find_package(LayerShellQt CONFIG QUIET)
if(LayerShellQt_FOUND)
    target_link_libraries(bugos-shell PRIVATE LayerShellQt::Interface)
    target_compile_definitions(bugos-shell PRIVATE BUGOS_LAYERSHELL)
    # Vanaf 6.6 kan een laag vast aan een scherm (Window::setScreen): de taakbalk van elk scherm blijft op dat scherm.
    if(LayerShellQt_VERSION VERSION_GREATER_EQUAL 6.6)
        target_compile_definitions(bugos-shell PRIVATE BUGOS_LAYERSHELL_SCHERM)
    endif()
    message(STATUS "bugos-shell: met layer-shell ${LayerShellQt_VERSION}")
elseif(BUGOS_LAYERSHELL_VERPLICHT)
    message(FATAL_ERROR "bugos-shell: layer-shell-qt niet gevonden (layer-shell-qt-devel)")
endif()
install(TARGETS bugos-shell RUNTIME DESTINATION bin)

# De test van het systeemvak (tools/test_shell_dbus.sh): alleen met -DBUGOS_TESTS=ON, niet in BugOS zelf.
option(BUGOS_TESTS "Testprogramma's bouwen" OFF)
if(BUGOS_TESTS)
    add_executable(systeemvak-test test/systeemvak_test.cpp src/systeemvak.cpp)
    target_link_libraries(systeemvak-test PRIVATE Qt6::Core Qt6::Gui Qt6::Quick Qt6::DBus)
    # Een nagemaakte kglobalaccel: meldt de schil de Windows-toets aan, en opent hij dan het startmenu?
    add_executable(kglobalaccel-nep test/kglobalaccel_nep.cpp)
    target_link_libraries(kglobalaccel-nep PRIVATE Qt6::Core Qt6::DBus)
endif()
