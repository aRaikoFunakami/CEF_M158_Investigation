// Copyright (c) 2026 The Chromium Embedded Framework Authors. All rights
// reserved. Use of this source code is governed by a BSD-style license that
// can be found in the LICENSE file.

// Footprint F3a: built instead of print_settings_impl.cc when
// enable_printing=false. CefPrintSettings::Create() is part of the public API
// and is referenced from libcef_dll, so it must exist. //printing is not
// available in this configuration so no object can be created.

#include "cef/include/cef_print_settings.h"

// static
CefRefPtr<CefPrintSettings> CefPrintSettings::Create() {
  return nullptr;
}
