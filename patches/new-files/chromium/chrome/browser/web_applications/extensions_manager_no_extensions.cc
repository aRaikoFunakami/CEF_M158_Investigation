// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// ExtensionsManager for builds without extensions (enable_extensions=false).
// The real implementation lives in
// //chrome/browser/web_applications/extensions, which is not built in that
// configuration. This one answers every query as "no extension exists".

#include <memory>
#include <string>
#include <unordered_set>
#include <utility>

#include "base/files/file_path.h"
#include "base/functional/callback.h"
#include "base/location.h"
#include "base/task/sequenced_task_runner.h"
#include "chrome/browser/web_applications/extensions_manager.h"
#include "chrome/browser/web_applications/mojom/user_display_mode.mojom.h"
#include "chrome/browser/web_applications/os_integration/web_app_shortcut.h"
#include "extensions/buildflags/buildflags.h"

static_assert(!BUILDFLAG(ENABLE_EXTENSIONS));

namespace web_app {

namespace {

class NoExtensionsManager : public ExtensionsManager {
 public:
  NoExtensionsManager() = default;
  ~NoExtensionsManager() override = default;

  // There is no extension system to wait for. Stay asynchronous like the real
  // implementation (OneShotEvent::Post).
  void OnExtensionSystemReady(base::OnceClosure on_ready) override {
    base::SequencedTaskRunner::GetCurrentDefault()->PostTask(
        FROM_HERE, std::move(on_ready));
  }

  std::unordered_set<base::FilePath> GetIsolatedStoragePaths() override {
    return {};
  }

  std::unique_ptr<ExtensionInstallGate> RegisterGarbageCollectionInstallGate()
      override {
    return std::make_unique<ExtensionInstallGate>();
  }

  bool IsExtensionBlockedByPolicy(const std::string& extension_id) override {
    return false;
  }
  bool IsExtensionInstalled(const std::string& extension_id) override {
    return false;
  }
  bool IsExtensionForceInstalled(const std::string& extension_id,
                                 std::u16string* reason) override {
    return false;
  }
  bool IsExtensionDefaultInstalled(const std::string& extension_id) override {
    return false;
  }
  bool IsExternalExtensionUninstalled(
      const std::string& extension_id) override {
    return false;
  }
  bool DidPreinstalledAppsPerformNewInstallation() override { return false; }
  bool IsPreinstalledExtensionAppId(const std::string& app_id) override {
    return false;
  }

  void CopyAppSortingLayout(const std::string& from_extension_id,
                            const std::string& to_web_app_id) override {}

  // The callers only reach the two functions below after
  // IsExtensionInstalled() returned true, which never happens here.
  mojom::UserDisplayMode GetExtensionUserDisplayMode(
      const std::string& extension_id) override {
    return mojom::UserDisplayMode::kBrowser;
  }
  std::unique_ptr<ShortcutInfo> GetExtensionShortcutInfo(
      const std::string& extension_id) override {
    return nullptr;
  }

  void WaitForExtensionShortcutsDeleted(const std::string& extension_id,
                                        base::OnceClosure callback) override {
    std::move(callback).Run();
  }
};

}  // namespace

// static
std::unique_ptr<ExtensionsManager> ExtensionsManager::CreateForProfile(
    Profile* profile) {
  return std::make_unique<NoExtensionsManager>();
}

// ExtensionsManager::GetExtensionSystemSharedFactory() is intentionally not
// defined: there is no extension system factory to depend on, and its only
// caller (WebAppProviderFactory) is compiled out.

}  // namespace web_app
