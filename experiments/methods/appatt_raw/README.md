# APPATT Raw Matrix Method

`appatt_raw` is a thin preserved benchmark alias around the already validated raw APPATT implementation in `methods/appatt/method.py`.

It delegates matrix construction to `APPATTMatrixBuilder` and does not add smoothing, shortcutting, fallback routing, parallelization, or any independent SETG-TG search logic. The purpose of this method name is to make the raw-versus-smoothed APPATT experiment explicit while leaving the existing `appatt` method and outputs intact.
