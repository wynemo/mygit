use gpui::{App, Bounds, DisplayId, Pixels, point, px, size};

pub fn placement(cx: &App) -> (Option<DisplayId>, Bounds<Pixels>) {
    #[cfg(target_os = "windows")]
    if let Some(placement) = windows_placement(cx) {
        return placement;
    }
    let display = cx.primary_display();
    let id = display.as_ref().map(|display| display.id());
    let bounds = display
        .map(|display| fit(display.bounds()))
        .unwrap_or_else(|| Bounds::centered(None, size(px(1200.), px(800.)), cx));
    (id, bounds)
}

fn fit(area: Bounds<Pixels>) -> Bounds<Pixels> {
    let dimensions = size(
        px(1200.).min(area.size.width * 0.9),
        px(800.).min(area.size.height * 0.9),
    );
    Bounds::new(
        point(
            area.origin.x + (area.size.width - dimensions.width) / 2.,
            area.origin.y + (area.size.height - dimensions.height) / 2.,
        ),
        dimensions,
    )
}

#[cfg(target_os = "windows")]
fn windows_placement(cx: &App) -> Option<(Option<DisplayId>, Bounds<Pixels>)> {
    use windows::Win32::{
        Foundation::{LPARAM, POINT, RECT},
        Graphics::Gdi::{
            EnumDisplayMonitors, GetMonitorInfoW, HDC, HMONITOR, MONITOR_DEFAULTTONEAREST,
            MONITORINFO, MonitorFromPoint,
        },
        UI::WindowsAndMessaging::GetCursorPos,
    };

    use windows::core::BOOL;

    unsafe extern "system" fn collect(
        monitor: HMONITOR,
        _: HDC,
        _: *mut RECT,
        data: LPARAM,
    ) -> BOOL {
        let monitors = unsafe { &mut *(data.0 as *mut Vec<HMONITOR>) };
        monitors.push(monitor);
        BOOL(1)
    }

    let mut cursor = POINT::default();
    // GPUI uses the same EnumDisplayMonitors order for its DisplayIds.
    let mut monitors = Vec::<HMONITOR>::new();
    let mut info = MONITORINFO {
        cbSize: std::mem::size_of::<MONITORINFO>() as u32,
        ..Default::default()
    };
    let monitor = unsafe {
        GetCursorPos(&mut cursor).ok()?;
        let monitor = MonitorFromPoint(cursor, MONITOR_DEFAULTTONEAREST);
        EnumDisplayMonitors(
            None,
            None,
            Some(collect),
            LPARAM(&mut monitors as *mut _ as isize),
        )
        .ok()?;
        GetMonitorInfoW(monitor, &mut info).ok()?;
        monitor
    };
    let index = monitors
        .iter()
        .position(|candidate| *candidate == monitor)?;
    let display = cx
        .displays()
        .into_iter()
        .find(|display| u32::from(display.id()) == index as u32)?;
    // Convert physical screen coordinates using this monitor's DPI, including
    // negative origins and mixed scaling across monitors.
    let scale = (info.rcMonitor.right - info.rcMonitor.left) as f32
        / f32::from(display.bounds().size.width);
    let work = info.rcWork;
    let area = Bounds::new(
        point(px(work.left as f32 / scale), px(work.top as f32 / scale)),
        size(
            px((work.right - work.left) as f32 / scale),
            px((work.bottom - work.top) as f32 / scale),
        ),
    );
    Some((Some(display.id()), fit(area)))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn placement_fits_small_and_negative_origin_displays() {
        for area in [
            Bounds::new(point(px(-1920.), px(-200.)), size(px(1920.), px(1040.))),
            Bounds::new(point(px(0.), px(0.)), size(px(800.), px(600.))),
            Bounds::new(point(px(0.), px(0.)), size(px(3440.), px(1440.))),
        ] {
            let bounds = fit(area);
            assert!(bounds.size.width <= px(1200.));
            assert!(bounds.size.height <= px(800.));
            assert!(bounds.left() >= area.left() && bounds.right() <= area.right());
            assert!(bounds.top() >= area.top() && bounds.bottom() <= area.bottom());
            assert_eq!(bounds.center(), area.center());
        }
    }
}
