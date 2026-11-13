// Footprint 調査(E3b): 外した Blink モジュールのうち、//chrome から参照が残る公開関数のスタブ。
#include "third_party/blink/public/web/modules/credentialmanagement/throttle_helper.h"

namespace blink {

// FedCM(credentialmanagement)を外したので何もしない。
void SetIdpSigninStatus(const LocalFrameToken& local_frame_token,
                        const url::Origin& origin,
                        mojom::IdpSigninStatus status) {}

}  // namespace blink
