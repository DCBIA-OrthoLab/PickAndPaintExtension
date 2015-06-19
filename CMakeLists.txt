cmake_minimum_required(VERSION 2.8.9)

project(PickAndPaintExtension)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "http://www.example.com/Slicer/Extensions/PickAndPaintExtension")
set(EXTENSION_CATEGORY "Shape Analysis")
set(EXTENSION_CONTRIBUTORS "Lucie Macron (University of Michigan)")
set(EXTENSION_DESCRIPTION "Pick 'n Paint tool allows users to select ROIs on a reference model and to propagate it over different time point models.")
set(EXTENSION_ICONURL "http://www.example.com/Slicer/Extensions/PickAndPaintExtension.png")
set(EXTENSION_SCREENSHOTURLS "http://www.example.com/Slicer/Extensions/PickAndPaintExtension/Screenshots/1.png")

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(PickAndPaint)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_CPACK})
