//! Native kernels for the DWG scene build (flat.py / build.py hot loops). Every function mirrors a Python original
//! operation-for-operation so results are bit-identical (tests/parity.py).
mod bits;
use pyo3::prelude::*;
use pyo3::types::{PyFloat, PyInt, PyList};
use std::f64::consts::PI;

/// Python round(x, n) for n <= 6: correctly rounded half-even, same doubles as CPython.
#[inline]
fn pyround(x: f64, n: i32) -> f64 {
    if !x.is_finite() || x.abs() >= 1e12 {
        if !x.is_finite() { return x; }
        return format!("{:.*}", n as usize, x).parse().unwrap_or(x);
    }
    let p = 10f64.powi(n);
    let y = x * p;
    let r = y.round_ties_even();
    if ((y - r).abs() - 0.5).abs() > 1e-6 {
        let v = r / p;
        // keep -0.0 sign like CPython (round(-0.0001, 3) == -0.0)
        return if v == 0.0 && x.is_sign_negative() { -0.0 } else { v };
    }
    format!("{:.*}", n as usize, x).parse().unwrap_or(x)
}

#[pyfunction]
#[pyo3(signature = (v, n=3))]
fn round_list<'py>(py: Python<'py>, v: &Bound<'py, PyAny>, n: i32) -> PyResult<Bound<'py, PyList>> {
    let out = PyList::empty_bound(py);
    for x in v.iter()? {
        let x = x?;
        if x.is_exact_instance_of::<PyFloat>() { out.append(pyround(x.extract::<f64>()?, n))?; }
        else if x.is_exact_instance_of::<PyInt>() { out.append(x)?; }          // round(int, n) is the same int
        else { return Err(pyo3::exceptions::PyTypeError::new_err("round_list: float or int expected")); }
    }
    Ok(out)
}

type M = (f64, f64, f64, f64, f64, f64); // a b c d tx ty (Mat.apply: (a*x+b*y+tx, c*x+d*y+ty))

#[inline]
fn ap(m: &M, x: f64, y: f64) -> (f64, f64) {
    (m.0 * x + m.1 * y + m.4, m.2 * x + m.3 * y + m.5)
}

/// ocs axes for an extrusion normal (dwgscene.ocs_axes), passed in from Python
type Ax = ((f64, f64, f64), (f64, f64, f64), (f64, f64, f64));

#[inline]
fn wpt(m: &M, ax: &Option<Ax>, x: f64, y: f64, z: f64) -> (f64, f64) {
    match ax {
        None => ap(m, x, y),
        Some((a, b, c)) => ap(m, a.0 * x + b.0 * y + c.0 * z, a.1 * x + b.1 * y + c.1 * z),
    }
}

fn arc_raw(cx: f64, cy: f64, r: f64, a0: f64, mut a1: f64, ccw: bool) -> Vec<(f64, f64)> {
    if ccw { while a1 <= a0 { a1 += 2.0 * PI; } } else { while a1 >= a0 { a1 -= 2.0 * PI; } }
    let n = std::cmp::max(8, ((a1 - a0).abs() / (2.0 * PI) * 64.0) as i64 + 1);
    (0..=n).map(|i| {
        let t = a0 + (a1 - a0) * (i as f64) / (n as f64);
        (cx + r * t.cos(), cy + r * t.sin())
    }).collect()
}

fn bulge_raw(p0: (f64, f64), p1: (f64, f64), bulge: f64) -> Vec<(f64, f64)> {
    if bulge.abs() < 1e-12 { return vec![p1]; }
    let (dx, dy) = (p1.0 - p0.0, p1.1 - p0.1);
    let d = dx.hypot(dy);
    if d == 0.0 { return vec![p1]; }
    let theta = 4.0 * bulge.atan();
    let r = d / (2.0 * (theta / 2.0).sin());
    let (mx, my) = ((p0.0 + p1.0) / 2.0, (p0.1 + p1.1) / 2.0);
    let h = r * (theta / 2.0).cos();
    let (nx, ny) = (-dy / d, dx / d);
    let (cx, cy) = (mx + nx * h, my + ny * h);
    let a0 = (p0.1 - cy).atan2(p0.0 - cx);
    let m = std::cmp::max(2, (theta.abs() / (2.0 * PI) * 64.0) as i64 + 1);
    let mut pts: Vec<(f64, f64)> = (1..=m).map(|i| {
        let a = a0 + theta * (i as f64) / (m as f64);
        (cx + r.abs() * a.cos(), cy + r.abs() * a.sin())
    }).collect();
    *pts.last_mut().unwrap() = p1;
    pts
}

fn flat(pts: Vec<(f64, f64)>) -> Vec<f64> {
    let mut f = Vec::with_capacity(pts.len() * 2);
    for (x, y) in pts { f.push(x); f.push(y); }
    f
}

/// flat transformed points of a CIRCLE (a0=0,a1=2pi) or ARC: flat._entity
#[pyfunction]
#[pyo3(signature = (c, r, a0, a1, mat, ax=None))]
fn arc_flat(c: (f64, f64, f64), r: f64, a0: f64, a1: f64, mat: M, ax: Option<Ax>) -> Vec<f64> {
    flat(arc_raw(c.0, c.1, r, a0, a1, true).into_iter().map(|(x, y)| wpt(&mat, &ax, x, y, c.2)).collect())
}

/// flat.py _ell_pts, flattened
#[pyfunction]
fn ell_flat(c: (f64, f64, f64), mj: (f64, f64, f64), r: f64, a0: f64, mut a1: f64, mat: M) -> Vec<f64> {
    if a1 <= a0 { a1 += 2.0 * PI; }
    let n = std::cmp::max(24, ((a1 - a0) / (2.0 * PI) * 96.0) as i64);
    let (a, b) = (mj.0, mj.1);
    let mut out = Vec::with_capacity((n as usize + 1) * 2);
    for i in 0..=n {
        let t = a0 + (a1 - a0) * (i as f64) / (n as f64);
        let (x, y) = ap(&mat, c.0 + a * t.cos() - b * r * t.sin(), c.1 + b * t.cos() + a * r * t.sin());
        out.push(x); out.push(y);
    }
    out
}

/// LWPOLYLINE centre path without widths (flat.py LWPOLYLINE branch): flat transformed points
#[pyfunction]
#[pyo3(signature = (pts, bul, closed, elev, mat, ax=None))]
fn lwpoly_path(pts: Vec<(f64, f64)>, bul: Vec<f64>, closed: bool, elev: f64, mat: M, ax: Option<Ax>) -> Vec<f64> {
    let n = pts.len();
    if n == 0 { return vec![]; }
    let mut path = vec![wpt(&mat, &ax, pts[0].0, pts[0].1, elev)];
    let last = n + if closed { 1 } else { 0 };
    for i in 1..last {
        let p0 = pts[i - 1]; let p1 = pts[i % n];
        let b = if i - 1 < bul.len() { bul[i - 1] } else { 0.0 };
        for q in bulge_raw(p0, p1, b) { path.push(wpt(&mat, &ax, q.0, q.1, elev)); }
    }
    flat(path)
}

/// Mat.apply over a flat list [x0,y0,x1,y1,...]
#[pyfunction]
fn apply_flat(v: Vec<f64>, mat: M) -> Vec<f64> {
    let mut o = Vec::with_capacity(v.len());
    for c in v.chunks_exact(2) { let (x, y) = ap(&mat, c[0], c[1]); o.push(x); o.push(y); }
    o
}


// ---- json.dumps(obj, separators=(',', ':')) clone (ensure_ascii, allow_nan) ----
use pyo3::types::{PyBool, PyDict, PyString, PyTuple};

fn py_float_repr(x: f64, out: &mut String) {
    if x.is_nan() { out.push_str("NaN"); return; }
    if x.is_infinite() { out.push_str(if x > 0.0 { "Infinity" } else { "-Infinity" }); return; }
    if x == 0.0 { out.push_str(if x.is_sign_negative() { "-0.0" } else { "0.0" }); return; }
    let mut e = format!("{:e}", x.abs());           // shortest round-trip digits: d.ddde<exp>
    let nd0 = e.split_once('e').unwrap().0.chars().filter(|c| *c != '.').count();
    if nd0 >= 16 {    // exact ties: Rust rounds the last digit up, CPython half-even; redo at the same length with correct rounding
        let alt = format!("{:.*e}", nd0 - 1, x.abs());
        if alt.parse::<f64>().ok() == Some(x.abs()) { e = alt; }
    }
    let (m, ex) = e.split_once('e').unwrap();
    let ex: i32 = ex.parse().unwrap();
    let digits: String = m.chars().filter(|c| *c != '.').collect();
    if x < 0.0 { out.push('-'); }
    let nd = digits.len() as i32;
    if -4 <= ex && ex < 16 {
        if ex >= 0 {
            if nd <= ex + 1 { out.push_str(&digits); for _ in 0..(ex + 1 - nd) { out.push('0'); } out.push_str(".0"); }
            else { out.push_str(&digits[..(ex + 1) as usize]); out.push('.'); out.push_str(&digits[(ex + 1) as usize..]); }
        } else {
            out.push_str("0."); for _ in 0..(-ex - 1) { out.push('0'); } out.push_str(&digits);
        }
    } else {
        out.push_str(&digits[..1]);
        if nd > 1 { out.push('.'); out.push_str(&digits[1..]); }
        out.push('e'); out.push(if ex < 0 { '-' } else { '+' });
        let a = ex.abs(); if a < 10 { out.push('0'); } out.push_str(&a.to_string());
    }
}

fn json_str(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""), '\\' => out.push_str("\\\\"), '\n' => out.push_str("\\n"), '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"), '\u{8}' => out.push_str("\\b"), '\u{c}' => out.push_str("\\f"),
            c if (c as u32) < 0x20 || (c as u32) > 0x7e => {
                let mut b = [0u16; 2];
                for u in c.encode_utf16(&mut b) { out.push_str(&format!("\\u{:04x}", u)); }
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

fn ser(o: &Bound<'_, PyAny>, out: &mut String) -> PyResult<()> {
    if o.is_none() { out.push_str("null"); }
    else if let Ok(b) = o.downcast::<PyBool>() { out.push_str(if b.is_true() { "true" } else { "false" }); }
    else if o.is_exact_instance_of::<PyInt>() { out.push_str(&o.str()?.to_cow()?); }
    else if o.is_exact_instance_of::<PyFloat>() { py_float_repr(o.extract::<f64>()?, out); }
    else if let Ok(s) = o.downcast::<PyString>() { json_str(&s.to_cow()?, out); }
    else if let Ok(d) = o.downcast::<PyDict>() {
        out.push('{'); let mut first = true;
        for (k, v) in d.iter() {
            if !first { out.push(','); } first = false;
            if let Ok(s) = k.downcast::<PyString>() { json_str(&s.to_cow()?, out); }
            else if k.is_exact_instance_of::<PyInt>() { out.push('"'); out.push_str(&k.str()?.to_cow()?); out.push('"'); }
            else { return Err(pyo3::exceptions::PyTypeError::new_err("unsupported dict key")); }
            out.push(':'); ser(&v, out)?;
        }
        out.push('}');
    }
    else if let Ok(l) = o.downcast::<PyList>() {
        out.push('['); let mut first = true;
        for v in l.iter() { if !first { out.push(','); } first = false; ser(&v, out)?; }
        out.push(']');
    }
    else if let Ok(l) = o.downcast::<PyTuple>() {
        out.push('['); let mut first = true;
        for v in l.iter() { if !first { out.push(','); } first = false; ser(&v, out)?; }
        out.push(']');
    }
    else { return Err(pyo3::exceptions::PyTypeError::new_err("unsupported type")); }
    Ok(())
}

/// json.dumps(obj, separators=(',', ':')).encode(); raises TypeError for anything else (caller falls back to Python)
#[pyfunction]
fn dumps(py: Python<'_>, o: &Bound<'_, PyAny>) -> PyResult<Py<pyo3::types::PyBytes>> {
    let mut s = String::with_capacity(1 << 20);
    ser(o, &mut s)?;
    Ok(pyo3::types::PyBytes::new_bound(py, s.as_bytes()).unbind())
}



/// flat.py bspline_fast (scalar Piegl-Tiller order, bit-identical to the numpy path): samples as (x, y)
fn bspline_samples(deg: usize, knots: &[f64], ctrl: &[(f64, f64)], weights: Option<&[f64]>) -> Vec<(f64, f64)> {
    let m = ctrl.len();
    if m == 0 || knots.len() < m + deg + 1 || deg < 1 { return ctrl.to_vec(); }
    let (t0, t1) = (knots[deg], knots[m]);
    let n = std::cmp::max(16, 6 * m);
    let mut pts = Vec::with_capacity(n + 1);
    let mut nn = vec![0.0f64; deg + 1]; let mut left = vec![0.0f64; deg + 1]; let mut right = vec![0.0f64; deg + 1];
    for s_ in 0..=n {
        let t = t0 + (t1 - t0) * (s_ as f64) / (n as f64);
        let bs = knots.partition_point(|k| *k <= t);           // bisect_right
        let span = std::cmp::min(std::cmp::max(bs as i64 - 1, deg as i64), m as i64 - 1) as usize;
        for v in nn.iter_mut() { *v = 0.0; } nn[0] = 1.0;
        for j in 1..=deg {
            left[j] = t - knots[span + 1 - j]; right[j] = knots[span + j] - t;
            let mut saved = 0.0;
            for r in 0..j {
                let den = right[r + 1] + left[j - r];
                let tmp = if den != 0.0 { nn[r] / den } else { 0.0 };
                nn[r] = saved + right[r + 1] * tmp;
                saved = left[j - r] * tmp;
            }
            nn[j] = saved;
        }
        let (mut x, mut y, mut w) = (0.0, 0.0, 0.0);
        for j in 0..=deg {
            let i = span + j - deg;
            let wi = match weights { Some(ws) => nn[j] * ws[i], None => nn[j] };
            x += wi * ctrl[i].0; y += wi * ctrl[i].1; w += wi;
        }
        if w != 0.0 { pts.push((x / w, y / w)); }
    }
    pts
}

// ---- whole-block fast path for flat.py Flattener.flatten (simple kinds) ----
use pyo3::types::{PySet, PyAny as PA};

fn fnum(e: &Bound<'_, PyDict>, k: &str) -> Option<f64> {
    e.get_item(k).ok().flatten().and_then(|v| if v.is_exact_instance_of::<PyFloat>() || v.is_exact_instance_of::<PyInt>() { v.extract::<f64>().ok() } else { None })
}
fn fvec(e: &Bound<'_, PyDict>, k: &str, n: usize) -> Option<Vec<f64>> {
    let v = e.get_item(k).ok().flatten()?;
    let mut out = Vec::with_capacity(n);
    let it = v.iter().ok()?;
    for x in it { let x = x.ok()?; if !(x.is_exact_instance_of::<PyFloat>() || x.is_exact_instance_of::<PyInt>()) { return None; } out.push(x.extract::<f64>().ok()?); if out.len() == n { break; } }
    if out.len() < n { None } else { Some(out) }
}
fn ok_xy(v: &[f64]) -> bool { v.iter().all(|c| c.abs() < 1e12) }

/// Process `content` (entity dicts of one block). Returns a list: a primitive tuple for every entity done here,
/// or the entity's INDEX (int) for anything the Python path must handle (order preserved).
#[pyfunction]
fn flatten_block<'py>(py: Python<'py>, content: &Bound<'py, PyList>, mat: M, hide: &Bound<'py, PySet>, dscale: f64,
                      top: bool, cache: &Bound<'py, PyDict>, miss: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
    let out = PyList::empty_bound(py);
    for (idx, ent) in content.iter().enumerate() {
        let e = match ent.downcast::<PyDict>() { Ok(d) => d, Err(_) => { out.append(idx)?; continue; } };
        let fallback = |out: &Bound<'py, PyList>| -> PyResult<()> { out.append(idx) };
        let kind: String = match e.get_item("kind")? { Some(k) => k.extract()?, None => { fallback(&out)?; continue; } };
        let kd = kind.as_str();
        if !matches!(kd, "LINE" | "CIRCLE" | "ARC" | "ELLIPSE" | "LWPOLYLINE" | "POINT" | "SOLID" | "TRACE" | "SPLINE") { fallback(&out)?; continue; }
        if matches!(kd, "CIRCLE" | "ARC" | "LWPOLYLINE" | "SOLID" | "TRACE") { if let Some(x) = e.get_item("ext")? { let t: Option<Vec<f64>> = x.extract().ok(); if t.as_deref() != Some(&[0.0, 0.0, 1.0][..]) { fallback(&out)?; continue; } } }
        let colv = match e.get_item("color")? { Some(c) => c, None => { fallback(&out)?; continue; } };
        let ncol = colv.len()?;
        if ncol > 2 && !colv.get_item(2)?.is_none() && colv.get_item(2)?.is_truthy()? { fallback(&out)?; continue; }   // transparency
        let key = PyTuple::new_bound(py, [
            e.get_item("layer")?.map_or(py.None().into_bound(py), |v| v),
            PyTuple::new_bound(py, colv.iter()?.map(|x| x.unwrap()).collect::<Vec<_>>()).into_any(),
            e.get_item("lweight")?.map_or(py.None().into_bound(py), |v| v),
            e.get_item("ltflags")?.map_or(py.None().into_bound(py), |v| v),
            e.get_item("ltype_index")?.map_or(py.None().into_bound(py), |v| v),
            // linetype by object (ltflags == 3): the LTYPE is found through the entity's own handles, so the entity handle is part of the key
            match e.get_item("ltflags")? { Some(f) if f.extract::<i64>().ok() == Some(3) => e.get_item("handle")?.map_or(py.None().into_bound(py), |v| v), _ => py.None().into_bound(py) },
        ]);
        let ent_res: Bound<'py, PA> = match cache.get_item(&key)? {
            Some(v) => v,
            None => { let r = miss.call1((e,))?; cache.set_item(&key, &r)?; r }
        };
        if ent_res.is_none() { fallback(&out)?; continue; }
        let ly = ent_res.get_item(0)?; let col = ent_res.get_item(1)?; let lw = ent_res.get_item(2)?;
        let ds = ent_res.get_item(3)?; let ltsc: f64 = ent_res.get_item(4)?.extract()?;
        if hide.contains(&ly)? { continue; }
        if e.get_item("invis")?.map_or(false, |v| v.is_truthy().unwrap_or(false)) { continue; }
        let hd = match e.get_item("handle")? { Some(h) => h, None => { fallback(&out)?; continue; } };
        // geometry
        let flatpts: Vec<f64> = match kd {
            "LINE" => {
                let (p1, p2) = match (fvec(e, "p1", 2), fvec(e, "p2", 2)) { (Some(a), Some(b)) => (a, b), _ => { fallback(&out)?; continue; } };
                if !ok_xy(&p1) || !ok_xy(&p2) { fallback(&out)?; continue; }
                let a = ap(&mat, p1[0], p1[1]); let b = ap(&mat, p2[0], p2[1]);
                vec![a.0, a.1, b.0, b.1]
            }
            "CIRCLE" | "ARC" => {
                let (c, r) = match (fvec(e, "center", 3), fnum(e, "radius")) { (Some(c), Some(r)) => (c, r), _ => { fallback(&out)?; continue; } };
                if !ok_xy(&c) || !(r.abs() < 1e12) { fallback(&out)?; continue; }
                let (a0, a1) = if kd == "CIRCLE" { (0.0, 2.0 * PI) } else { match (fnum(e, "a0"), fnum(e, "a1")) { (Some(a), Some(b)) => (a, b), _ => { fallback(&out)?; continue; } } };
                if !a0.is_finite() || !a1.is_finite() || (a1 - a0).abs() > 1e6 { fallback(&out)?; continue; }
                arc_flat((c[0], c[1], c[2]), r, a0, a1, mat, None)
            }
            "POINT" => {
                let p = match fvec(e, "p", 2) { Some(p) => p, None => { fallback(&out)?; continue; } };
                if !ok_xy(&p) { fallback(&out)?; continue; }
                let (x, y) = ap(&mat, p[0], p[1]);
                if !(x.abs() < 1e12 && y.abs() < 1e12) { fallback(&out)?; continue; }
                let mut items: Vec<Bound<'py, PA>> = vec![PyString::new_bound(py, "p").into_any(), ly, col, PyFloat::new_bound(py, x).into_any(), PyFloat::new_bound(py, y).into_any(), hd.clone()];
                if top { items.push(hd); }
                out.append(PyTuple::new_bound(py, items))?;
                continue;
            }
            "SOLID" | "TRACE" => {
                let ptsv = match e.get_item("pts")? { Some(p) => p, None => { fallback(&out)?; continue; } };
                let mut q: Vec<(f64, f64)> = Vec::new(); let mut bad = false;
                for p in ptsv.iter()? { let p = p?; match (p.get_item(0).ok().and_then(|v| v.extract::<f64>().ok()), p.get_item(1).ok().and_then(|v| v.extract::<f64>().ok())) { (Some(x), Some(y)) => q.push((x, y)), _ => { bad = true; break; } } }
                if bad || q.len() < 4 { fallback(&out)?; continue; }
                let elev = match fnum(e, "elev") { Some(v) => v, None => { fallback(&out)?; continue; } };
                let mut f = Vec::with_capacity(8);
                for i in [0usize, 1, 3, 2] { let (x, y) = ap(&mat, q[i].0, q[i].1); f.push(x); f.push(y); }
                let _ = elev;
                if f.iter().any(|v| !(v.abs() < 1e12)) { fallback(&out)?; continue; }
                let info = PyDict::new_bound(py); info.set_item("solid", 1)?;
                let loops = PyList::new_bound(py, [PyList::new_bound(py, f)]);
                let mut items: Vec<Bound<'py, PA>> = vec![PyString::new_bound(py, "h").into_any(), ly, col, loops.into_any(), info.into_any(), hd.clone()];
                if top { items.push(hd); }
                out.append(PyTuple::new_bound(py, items))?;
                continue;
            }
            "SPLINE" => {
                let pairs = |k: &str| -> Option<Vec<(f64, f64)>> {
                    let v = e.get_item(k).ok().flatten()?; let mut o = Vec::new();
                    for p in v.iter().ok()? { let p = p.ok()?; o.push((p.get_item(0).ok()?.extract::<f64>().ok()?, p.get_item(1).ok()?.extract::<f64>().ok()?)); }
                    Some(o)
                };
                let ctrlv = match e.get_item("ctrl")? { Some(c) => c, None => { fallback(&out)?; continue; } };
                let pts: Vec<(f64, f64)> = if ctrlv.is_truthy()? {
                    let ctrl = match pairs("ctrl") { Some(c) => c, None => { fallback(&out)?; continue; } };
                    let deg = match e.get_item("degree")?.and_then(|v| v.extract::<i64>().ok()) { Some(d) if d >= 0 => d as usize, _ => { fallback(&out)?; continue; } };
                    let knots: Vec<f64> = match e.get_item("knots")?.and_then(|v| v.extract().ok()) { Some(k) => k, None => { fallback(&out)?; continue; } };
                    let wv = e.get_item("weights")?;
                    let weights: Option<Vec<f64>> = match &wv { Some(w) if w.is_truthy()? => match w.extract() { Ok(v) => Some(v), Err(_) => { fallback(&out)?; continue; } }, _ => None };
                    if let Some(w) = &weights { if w.len() < ctrl.len() { fallback(&out)?; continue; } }
                    if deg < 1 || knots.len() < ctrl.len() + deg + 1 { fallback(&out)?; continue; }
                    bspline_samples(deg, &knots, &ctrl, weights.as_deref())
                } else {
                    match pairs("fit") { Some(f) => f, None => { fallback(&out)?; continue; } }
                };
                let mut f = Vec::with_capacity(pts.len() * 2);
                for (x, y) in pts { let (a, b) = ap(&mat, x, y); f.push(a); f.push(b); }
                f
            }
            "ELLIPSE" => {
                let (c, mj, r, a0, a1) = match (fvec(e, "center", 3), fvec(e, "major", 3), fnum(e, "ratio"), fnum(e, "a0"), fnum(e, "a1")) {
                    (Some(c), Some(m), Some(r), Some(a), Some(b)) => (c, m, r, a, b), _ => { fallback(&out)?; continue; } };
                if !ok_xy(&c) || !ok_xy(&mj) || !a0.is_finite() || !a1.is_finite() || !r.is_finite() { fallback(&out)?; continue; }
                ell_flat((c[0], c[1], c[2]), (mj[0], mj[1], mj[2]), r, a0, a1, mat)
            }
            _ => { // LWPOLYLINE without widths
                let ptsv = match e.get_item("pts")? { Some(p) => p, None => { fallback(&out)?; continue; } };
                let mut pts: Vec<(f64, f64)> = Vec::new();
                let mut bad = false;
                for p in ptsv.iter()? { let p = p?; match (p.get_item(0).ok().and_then(|v| v.extract::<f64>().ok()), p.get_item(1).ok().and_then(|v| v.extract::<f64>().ok())) { (Some(x), Some(y)) => pts.push((x, y)), _ => { bad = true; break; } } }
                if bad || pts.is_empty() { fallback(&out)?; continue; }
                let bul: Vec<f64> = match e.get_item("bulges")? { Some(b) => match b.extract::<Vec<f64>>() { Ok(v) => v, Err(_) => { fallback(&out)?; continue; } }, None => { fallback(&out)?; continue; } };
                let cw = fnum(e, "constwidth").unwrap_or(0.0);
                let widths = e.get_item("widths")?;
                let mut has_w = cw > 0.0;
                if let Some(w) = widths { if w.is_truthy()? { has_w = true; } }
                if has_w { fallback(&out)?; continue; }
                let closed = e.get_item("closed")?.map_or(false, |v| v.is_truthy().unwrap_or(false));
                let elev = match fnum(e, "elev") { Some(v) => v, None => { fallback(&out)?; continue; } };
                if !ok_xy(&[elev]) || pts.iter().any(|p| !p.0.is_finite() || !p.1.is_finite()) { fallback(&out)?; continue; }
                lwpoly_path(pts, bul, closed, elev, mat, None)
            }
        };
        if flatpts.len() < 4 { continue; }                     // line(): fewer than 2 points draws nothing
        if flatpts.iter().any(|v| !(v.abs() < 1e12)) { fallback(&out)?; continue; }
        let dash: Bound<'py, PA> = if ds.is_none() { py.None().into_bound(py) } else {
            let k = ltsc * fnum(e, "ltscale").unwrap_or(1.0) * dscale;
            let l = PyList::empty_bound(py);
            for x in ds.iter()? { l.append(pyround(x?.extract::<f64>()? * k, 6))?; }
            l.into_any()
        };
        let fl = PyList::new_bound(py, flatpts);
        let wd = PyFloat::new_bound(py, 0.0);
        let mut items: Vec<Bound<'py, PA>> = vec![
            PyString::new_bound(py, "l").into_any(), ly, col, lw, dash, fl.into_any(), hd.clone(), wd.into_any()];
        if top { items.push(hd); }
        out.append(PyTuple::new_bound(py, items))?;
    }
    Ok(out)
}


/// build.Doc._row for 'l' and 'h' primitives in one pass. Returns (items, xs, ys): items[i] is the row list, or the int i for
/// a primitive the Python _row must handle (text / point / unusual); xs, ys are the unrounded coordinates of the rows built here.
#[pyfunction]
fn rows_batch<'py>(py: Python<'py>, prims: &Bound<'py, PyList>, lidx: &Bound<'py, PyDict>) -> PyResult<(Bound<'py, PyList>, Vec<f64>, Vec<f64>)> {
    let items = PyList::empty_bound(py);
    let (mut xs, mut ys) = (Vec::new(), Vec::new());
    for (i, p) in prims.iter().enumerate() {
        let t = match p.downcast::<PyTuple>() { Ok(t) => t, Err(_) => { items.append(i)?; continue; } };
        let k: String = t.get_item(0)?.extract()?;
        let ly = t.get_item(1)?;
        let li: Bound<'py, PyAny> = if ly.is_none() || !ly.is_truthy()? { (-1i64).into_py(py).into_bound(py) } else {
            match lidx.get_item(&ly)? { Some(v) => v, None => (-1i64).into_py(py).into_bound(py) } };
        if k == "l" && t.len() == 9 {
            let f = t.get_item(5)?;
            let fv: Vec<f64> = match f.extract() { Ok(v) => v, Err(_) => { items.append(i)?; continue; } };
            // exact-int lists keep Python's int rounding result: send to Python
            if f.iter()?.any(|x| x.map_or(true, |x| !x.is_exact_instance_of::<PyFloat>())) { items.append(i)?; continue; }
            for c in fv.chunks_exact(2) { xs.push(c[0]); ys.push(c[1]); }
            let wd = t.get_item(7)?;
            let wdv: Bound<'py, PyAny> = if wd.is_truthy()? { PyFloat::new_bound(py, pyround(wd.extract::<f64>()?, 4)).into_any() } else { 0i64.into_py(py).into_bound(py) };
            let dash = t.get_item(4)?;
            let dash: Bound<'py, PyAny> = if dash.is_truthy()? { dash } else { 0i64.into_py(py).into_bound(py) };
            let row = PyList::new_bound(py, [
                PyString::new_bound(py, "l").into_any(), li, t.get_item(2)?, t.get_item(3)?, dash,
                PyList::new_bound(py, fv.iter().map(|v| pyround(*v, 3))).into_any(), t.get_item(6)?, wdv, t.get_item(8)?]);
            items.append(row)?;
        } else { items.append(i)?; }
    }
    Ok((items, xs, ys))
}

#[pymodule]
fn dwgscene_fast(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(round_list, m)?)?;
    m.add_function(wrap_pyfunction!(arc_flat, m)?)?;
    m.add_function(wrap_pyfunction!(ell_flat, m)?)?;
    m.add_function(wrap_pyfunction!(lwpoly_path, m)?)?;
    m.add_function(wrap_pyfunction!(apply_flat, m)?)?;
    m.add_function(wrap_pyfunction!(dumps, m)?)?;
    m.add_class::<bits::Bits>()?;
    m.add_function(wrap_pyfunction!(flatten_block, m)?)?;
    m.add_function(wrap_pyfunction!(rows_batch, m)?)?;
    Ok(())
}
