// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "fixture_types.h"

struct PGM_BASE
{
    wxString language = wxS( "en" );
    wxString GetLanguageTag() const { return language; }
};

inline PGM_BASE& Pgm()
{
    static PGM_BASE fixture;
    return fixture;
}
