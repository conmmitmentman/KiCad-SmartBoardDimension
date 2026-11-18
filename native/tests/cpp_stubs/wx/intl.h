// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

enum { wxLANGUAGE_ENGLISH, wxLANGUAGE_JAPANESE };

struct wxLocale
{
    inline static int systemLanguage = wxLANGUAGE_ENGLISH;
    static int GetSystemLanguage() { return systemLanguage; }
};
