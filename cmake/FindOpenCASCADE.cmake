# This script finds OCCT Technology libraries.
# The script requires:
#  OCCT_DIR - root OCCT folder or folder with CMake configuration files
#
# Script will define the following variables on success:
#  OCCT_FOUND       - package is successfully found
#  OCCT_INCLUDE_DIR - directory with headers
#  OCCT_LIBRARY_DIR - directory with libraries for linker
#  OCCT_BINARY_DIR  - directory with DLLs
include(FindPackageHandleStandardArgs)

# MY_PLATFORM variable
math (EXPR MY_BITNESS "32 + 32*(${CMAKE_SIZEOF_VOID_P}/8)")
if (WIN32)
  set (MY_PLATFORM "win${MY_BITNESS}")
elseif(APPLE)
  set (MY_PLATFORM "mac")
else()
  set (MY_PLATFORM "lin")
endif()

# MY_PLATFORM_AND_COMPILER variable
if (MSVC)
  if (MSVC90)
    set (MY_COMPILER vc9)
  elseif (MSVC10)
    set (MY_COMPILER vc10)
  elseif (MSVC11)
    set (MY_COMPILER vc11)
  elseif (MSVC12)
    set (MY_COMPILER vc12)
  elseif (MSVC14)
    set (MY_COMPILER vc14)
  else()
    set (MY_COMPILER vc15)
    message (WARNING "Unknown msvc version. $$MY_COMPILER is used")
  endif()
elseif (DEFINED CMAKE_COMPILER_IS_GNUCC)
  set (MY_COMPILER gcc)
elseif (DEFINED CMAKE_COMPILER_IS_GNUCXX)
  set (MY_COMPILER gcc)
elseif (CMAKE_CXX_COMPILER_ID MATCHES "[Cc][Ll][Aa][Nn][Gg]")
  set (MY_COMPILER clang)
elseif (CMAKE_CXX_COMPILER_ID MATCHES "[Ii][Nn][Tt][Ee][Ll]")
  set (MY_COMPILER icc)
else()
  set (MY_COMPILER ${CMAKE_GENERATOR})
  string (REGEX REPLACE " " "" COMPILER ${MY_COMPILER})
endif()
set (MY_PLATFORM_AND_COMPILER "${MY_PLATFORM}/${MY_COMPILER}")

set (OCCT_DIR "" CACHE PATH "Path to Open CASCADE libraries.")

# default paths
set (OCCT_INCLUDE_DIR "${OCCT_DIR}/inc")
set (OCCT_LIBRARY_DIR "${OCCT_DIR}/${MY_PLATFORM_AND_COMPILER}/lib")
set (OCCT_BINARY_DIR  "${OCCT_DIR}/${MY_PLATFORM_AND_COMPILER}/bin")

# complete list of OCCT Toolkits (copy-paste from adm/UDLIST, since installed OCCT does not include UDLIST)
set (OCCT_TKLIST "")
set (OCCT_TKLIST ${OCCT_TKLIST} TKernel TKMath) # FoundationClasses
set (OCCT_TKLIST ${OCCT_TKLIST} TKG2d TKG3d TKGeomBase TKBRep) # ModelingData
set (OCCT_TKLIST ${OCCT_TKLIST} TKGeomAlgo TKTopAlgo TKPrim TKBO TKBool TKHLR TKFillet TKOffset TKFeat TKMesh TKXMesh TKShHealing) # ModelingAlgorithms
set (OCCT_TKLIST ${OCCT_TKLIST} TKService TKV3d TKOpenGl TKMeshVS TKIVtk TKD3DHost) # Visualization
set (OCCT_TKLIST ${OCCT_TKLIST} TKCDF TKLCAF TKCAF TKBinL TKXmlL TKBin TKXml TKStdL TKStd TKTObj TKBinTObj TKXmlTObj TKVCAF) # ApplicationFramework
set (OCCT_TKLIST ${OCCT_TKLIST} TKXSBase TKSTEPBase TKSTEPAttr TKSTEP209 TKSTEP TKIGES TKXCAF TKXDEIGES TKXDESTEP TKSTL TKVRML TKXmlXCAF TKBinXCAF TKRWMesh) # DataExchange
set (OCCT_TKLIST ${OCCT_TKLIST} TKDraw TKViewerTest) # Draw

# validate location of OCCT libraries and headers
set (OCCT_INCLUDE_DIR_FOUND)
set (OCCT_LIBRARY_DIR_FOUND)
set (OCCT_LIBRARY_DEBUG_DIR_FOUND)
set (OCCT_IMPLIB_SUFFIX ${CMAKE_STATIC_LIBRARY_SUFFIX})
set (OCCT_SHAREDLIB_RELEASE_FOUND)
set (OCCT_SHAREDLIB_DEBUG_FOUND)
if (EXISTS "${OCCT_INCLUDE_DIR}/Standard.hxx")
  set (OCCT_INCLUDE_DIR_FOUND ON)
endif()

if (EXISTS "${OCCT_LIBRARY_DIR}/${CMAKE_SHARED_LIBRARY_PREFIX}TKernel${CMAKE_STATIC_LIBRARY_SUFFIX}")
  set (OCCT_LIBRARY_DIR_FOUND ON)
elseif (NOT WIN32 AND EXISTS "${OCCT_LIBRARY_DIR}/${CMAKE_SHARED_LIBRARY_PREFIX}TKernel${CMAKE_SHARED_LIBRARY_SUFFIX}")
  set (OCCT_LIBRARY_DIR_FOUND ON)
  set (OCCT_IMPLIB_SUFFIX ${CMAKE_SHARED_LIBRARY_SUFFIX})
endif()

if (EXISTS "${OCCT_LIBRARY_DIR}d/${CMAKE_SHARED_LIBRARY_PREFIX}TKernel${CMAKE_STATIC_LIBRARY_SUFFIX}")
  set (OCCT_LIBRARY_DEBUG_DIR_FOUND ON)
elseif (NOT WIN32 AND EXISTS "${OCCT_LIBRARY_DIR}d/${CMAKE_SHARED_LIBRARY_PREFIX}TKernel${CMAKE_SHARED_LIBRARY_SUFFIX}")
  set (OCCT_LIBRARY_DEBUG_DIR_FOUND ON)
  set (OCCT_IMPLIB_SUFFIX ${CMAKE_SHARED_LIBRARY_SUFFIX})
elseif (OCCT_LIBRARY_DIR_FOUND)
  message (STATUS "Only release OCCT libraries have been found")
endif()

if (NOT OCCT_LIBRARY_DIR_FOUND AND OCCT_LIBRARY_DEBUG_DIR_FOUND)
  set (OCCT_LIBRARY_DIR_FOUND ON)
  message (WARNING "Only debug OCCT libraries have been found")
endif()

if (WIN32)
  if (EXISTS "${OCCT_BINARY_DIR}/${CMAKE_SHARED_LIBRARY_PREFIX}TKernel${CMAKE_SHARED_LIBRARY_SUFFIX}")
    set (OCCT_SHAREDLIB_RELEASE_FOUND ON)
  endif()
  if (EXISTS "${OCCT_BINARY_DIR}d/${CMAKE_SHARED_LIBRARY_PREFIX}TKernel${CMAKE_SHARED_LIBRARY_SUFFIX}")
    set (OCCT_SHAREDLIB_DEBUG_FOUND ON)
  endif()
else()
  if (EXISTS "${OCCT_LIBRARY_DIR}/${CMAKE_SHARED_LIBRARY_PREFIX}TKernel${CMAKE_SHARED_LIBRARY_SUFFIX}")
    set (OCCT_SHAREDLIB_RELEASE_FOUND ON)
  endif()
  if (EXISTS "${OCCT_LIBRARY_DIR}d/${CMAKE_SHARED_LIBRARY_PREFIX}TKernel${CMAKE_SHARED_LIBRARY_SUFFIX}")
    set (OCCT_SHAREDLIB_DEBUG_FOUND ON)
  endif()
endif()

if (OCCT_INCLUDE_DIR_FOUND AND OCCT_LIBRARY_DIR_FOUND)
  set (OCCT_FOUND ON)
  set (OCCT_INSTALL_PREFIX ${OCCT_DIR})

  # Define OCCT toolkits so that CMake can put absolute paths to linker;
  # the library existance is not checked here, since modules can be disabled.
  foreach (aLibIter ${OCCT_TKLIST})
    add_library (${aLibIter} SHARED IMPORTED)

    set_property (TARGET ${aLibIter} APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
    set_target_properties (${aLibIter} PROPERTIES IMPORTED_IMPLIB_RELEASE "${OCCT_LIBRARY_DIR}/${CMAKE_SHARED_LIBRARY_PREFIX}${aLibIter}${OCCT_IMPLIB_SUFFIX}")
    if (OCCT_SHAREDLIB_RELEASE_FOUND)
      if (WIN32)
        set_target_properties (${aLibIter} PROPERTIES IMPORTED_LOCATION_RELEASE "${OCCT_BINARY_DIR}/${CMAKE_SHARED_LIBRARY_PREFIX}${aLibIter}${CMAKE_SHARED_LIBRARY_SUFFIX}")
      else()
        set_target_properties (${aLibIter} PROPERTIES IMPORTED_LOCATION_RELEASE "${OCCT_LIBRARY_DIR}/${CMAKE_SHARED_LIBRARY_PREFIX}${aLibIter}${CMAKE_SHARED_LIBRARY_SUFFIX}")
      endif()
    endif()

    if (OCCT_LIBRARY_DEBUG_DIR_FOUND)
      set_property (TARGET ${aLibIter} APPEND PROPERTY IMPORTED_CONFIGURATIONS DEBUG)
      set_target_properties (${aLibIter} PROPERTIES IMPORTED_IMPLIB_DEBUG "${OCCT_LIBRARY_DIR}d/${CMAKE_SHARED_LIBRARY_PREFIX}${aLibIter}${OCCT_IMPLIB_SUFFIX}")
      if (OCCT_SHAREDLIB_DEBUG_FOUND)
        if (WIN32)
          set_target_properties (${aLibIter} PROPERTIES IMPORTED_LOCATION_DEBUG "${OCCT_BINARY_DIR}d/${CMAKE_SHARED_LIBRARY_PREFIX}${aLibIter}${CMAKE_SHARED_LIBRARY_SUFFIX}")
        else()
          set_target_properties (${aLibIter} PROPERTIES IMPORTED_LOCATION_DEBUG "${OCCT_LIBRARY_DIR}d/${CMAKE_SHARED_LIBRARY_PREFIX}${aLibIter}${CMAKE_SHARED_LIBRARY_SUFFIX}")
        endif()
      endif()
    endif()
  endforeach()
else()
  # fallback searching for CMake configs
  if (NOT "${OCCT_DIR}" STREQUAL "")
    set (anOcctDirBak "${OCCT_DIR}")
    find_package (OCCT CONFIG QUIET PATHS "${OCCT_DIR}" NO_DEFAULT_PATH)
    set (OCCT_DIR "${anOcctDirBak}" CACHE PATH "Path to Open CASCADE libraries." FORCE)
  else()
    find_package (OCCT CONFIG QUIET)
  endif()
endif()
