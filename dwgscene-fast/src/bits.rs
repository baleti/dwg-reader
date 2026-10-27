//! Drop-in native version of dwgbits.Bits (R13-R2000 bit-stream reader). Same results and same exception types as the Python class.
use pyo3::exceptions::{PyIndexError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyTuple};

#[pyclass(module = "dwgscene_fast")]
pub struct Bits {
    data: Py<PyBytes>,
    #[pyo3(get, set)]
    p: usize,
    #[pyo3(get)]
    n: usize,
}

const PAST: &str = "read past the end of the object";

impl Bits {
    #[inline]
    fn buf<'a>(&'a self, py: Python<'a>) -> &'a [u8] { self.data.bind(py).as_bytes() }

    #[inline]
    fn rbits(&mut self, py: Python<'_>, n: usize) -> PyResult<u128> {
        // 1 <= n <= 128
        let i = self.p; let end = i + n;
        if end > self.n { return Err(PyIndexError::new_err(PAST)); }
        let d = self.data.bind(py).as_bytes();
        let a = i >> 3; let b = (end + 7) >> 3;
        let mut v: u128 = 0;
        let mut acc_bits = 0usize;
        // accumulate bytes a..b into u128 (up to 17 bytes for n=128 unaligned): use u128 with care
        let nbytes = b - a;
        if nbytes <= 16 {
            for k in a..b { v = (v << 8) | d[k] as u128; }
            self.p = end;
            let shift = (b * 8 - end) as u32;
            let v = v >> shift;
            return Ok(if n == 128 { v } else { v & ((1u128 << n) - 1) });
        }
        // 17 bytes: n > 120 and unaligned; do it in two halves
        let _ = acc_bits; acc_bits = 0; let _ = acc_bits;
        let hi = n - 64;
        let h = self.rbits(py, hi)?; let l = self.rbits(py, 64)?;
        Ok((h << 64) | l)
    }

    #[inline]
    fn rbyte(&mut self, py: Python<'_>) -> PyResult<u8> {
        let i = self.p;
        if i + 8 > self.n { return Err(PyIndexError::new_err(PAST)); }
        let d = self.data.bind(py).as_bytes(); let a = i >> 3; let s = i & 7;
        self.p = i + 8;
        Ok(if s == 0 { d[a] } else { (((d[a] as u16) << 8 | d[a + 1] as u16) >> (8 - s)) as u8 })
    }

    fn raw<'py>(&mut self, py: Python<'py>, n: usize) -> PyResult<Vec<u8>> {
        let i = self.p; let end = i + 8 * n;
        if end > self.n { return Err(PyIndexError::new_err(PAST)); }
        let d = self.data.bind(py).as_bytes(); let a = i >> 3;
        self.p = end;
        if i & 7 == 0 { return Ok(d[a..a + n].to_vec()); }
        let s = i & 7;
        Ok((0..n).map(|k| (((d[a + k] as u16) << 8 | d[a + k + 1] as u16) >> (8 - s)) as u8).collect())
    }

    #[inline]
    fn bb(&mut self, py: Python<'_>) -> PyResult<u8> {
        let i = self.p;
        if i + 2 > self.n { return Err(PyIndexError::new_err(PAST)); }
        self.p = i + 2;
        let d = self.data.bind(py).as_bytes(); let a = i >> 3; let s = i & 7;
        Ok(if s < 7 { (d[a] >> (6 - s)) & 3 } else { ((((d[a] as u16) << 8) | d[a + 1] as u16) >> 7) as u8 & 3 })
    }

    fn rs(&mut self, py: Python<'_>) -> PyResult<u32> { let r = self.raw(py, 2)?; Ok(u16::from_le_bytes([r[0], r[1]]) as u32) }
    fn rl(&mut self, py: Python<'_>) -> PyResult<u64> { let r = self.raw(py, 4)?; Ok(u32::from_le_bytes([r[0], r[1], r[2], r[3]]) as u64) }
    fn rd(&mut self, py: Python<'_>) -> PyResult<f64> { let r = self.raw(py, 8)?; let mut a = [0u8; 8]; a.copy_from_slice(&r); Ok(f64::from_le_bytes(a)) }
    fn bs_(&mut self, py: Python<'_>) -> PyResult<u32> {
        Ok(match self.bb(py)? { 0 => self.rs(py)?, 1 => self.rbyte(py)? as u32, 2 => 0, _ => 256 })
    }
    fn bd_(&mut self, py: Python<'_>) -> PyResult<Option<f64>> {
        Ok(match self.bb(py)? { 0 => Some(self.rd(py)?), 1 => Some(1.0), 2 => Some(0.0), _ => None })
    }
}

#[pymethods]
impl Bits {
    #[new]
    #[pyo3(signature = (data, pos=0))]
    fn new(py: Python<'_>, data: &Bound<'_, PyAny>, pos: usize) -> PyResult<Self> {
        let b: Bound<'_, PyBytes> = match data.downcast::<PyBytes>() {
            Ok(b) => b.clone(),
            Err(_) => PyBytes::new_bound(py, &data.extract::<Vec<u8>>()?),
        };
        let n = b.as_bytes().len() * 8;
        Ok(Bits { data: b.unbind(), p: pos, n })
    }
    #[getter]
    fn d(&self, py: Python<'_>) -> Py<PyBytes> { self.data.clone_ref(py) }

    fn bit(&mut self, py: Python<'_>) -> PyResult<u8> {
        let i = self.p; self.p = i + 1;
        let d = self.data.bind(py).as_bytes();
        if (i >> 3) >= d.len() { return Err(PyIndexError::new_err("index out of range")); }
        Ok((d[i >> 3] >> (7 - (i & 7))) & 1)
    }
    #[pyo3(name = "B")]
    fn b_(&mut self, py: Python<'_>) -> PyResult<u8> { self.bit(py) }
    fn bits(&mut self, py: Python<'_>, n: i64) -> PyResult<u128> {
        if n <= 0 { return Ok(0); }
        if n > 128 { return Err(PyValueError::new_err("bits(): more than 128 bits")); }
        self.rbits(py, n as usize)
    }
    #[pyo3(signature = (n, unit_bits=1))]
    fn cnt(&self, py: Python<'_>, n: Option<i64>, unit_bits: i64) -> PyResult<i64> {
        let len = self.buf(py).len() as i64;
        match n {
            Some(v) if v >= 0 && v * unit_bits <= len * 8 - self.p as i64 => Ok(v),
            other => Err(PyValueError::new_err(format!("implausible count {}", match other { Some(v) => v.to_string(), None => "None".into() }))),
        }
    }
    fn rcs<'py>(&mut self, py: Python<'py>, n: i64) -> PyResult<Bound<'py, PyBytes>> {
        self.cnt(py, Some(n), 8)?;
        let r = self.raw(py, n as usize)?;
        Ok(PyBytes::new_bound(py, &r))
    }
    fn _raw<'py>(&mut self, py: Python<'py>, n: usize) -> PyResult<Bound<'py, PyBytes>> {
        let r = self.raw(py, n)?; Ok(PyBytes::new_bound(py, &r))
    }
    #[pyo3(name = "RC")] fn rc(&mut self, py: Python<'_>) -> PyResult<u8> { self.rbyte(py) }
    #[pyo3(name = "RS")] fn rs_py(&mut self, py: Python<'_>) -> PyResult<u32> { self.rs(py) }
    #[pyo3(name = "RL")] fn rl_py(&mut self, py: Python<'_>) -> PyResult<u64> { self.rl(py) }
    #[pyo3(name = "RD")] fn rd_py(&mut self, py: Python<'_>) -> PyResult<f64> { self.rd(py) }
    #[pyo3(name = "BB")] fn bb_py(&mut self, py: Python<'_>) -> PyResult<u8> { self.bb(py) }
    #[pyo3(name = "BS")] fn bs_py(&mut self, py: Python<'_>) -> PyResult<u32> { self.bs_(py) }
    #[pyo3(name = "BL")]
    fn bl_py(&mut self, py: Python<'_>) -> PyResult<Option<u64>> {
        Ok(match self.bb(py)? { 0 => Some(self.rl(py)?), 1 => Some(self.rbyte(py)? as u64), 2 => Some(0), _ => None })
    }
    #[pyo3(name = "BD")] fn bd_py(&mut self, py: Python<'_>) -> PyResult<Option<f64>> { self.bd_(py) }
    #[pyo3(name = "H")]
    fn h(&mut self, py: Python<'_>) -> PyResult<(u32, u128)> {
        let code = self.rbits(py, 4)? as u32; let n = self.rbits(py, 4)? as usize;
        if n == 0 { return Ok((code, 0)); }
        let r = self.raw(py, n)?; let mut v: u128 = 0; for b in r { v = (v << 8) | b as u128; }
        Ok((code, v))
    }
    #[pyo3(name = "DD")]
    fn dd(&mut self, py: Python<'_>, default: f64) -> PyResult<f64> {
        let c = self.bb(py)?;
        if c == 0 { return Ok(default); }
        if c == 3 { return self.rd(py); }
        let b = default.to_le_bytes();
        let mut nb = [0u8; 8];
        if c == 1 { let x = self.raw(py, 4)?; nb[..4].copy_from_slice(&x); nb[4..].copy_from_slice(&b[4..]); }
        else { let x = self.raw(py, 6)?; nb[..4].copy_from_slice(&x[2..6]); nb[4..6].copy_from_slice(&x[0..2]); nb[6..].copy_from_slice(&b[6..]); }
        Ok(f64::from_le_bytes(nb))
    }
    #[pyo3(name = "BT")]
    fn bt(&mut self, py: Python<'_>) -> PyResult<Option<f64>> { if self.bit(py)? != 0 { Ok(Some(0.0)) } else { self.bd_(py) } }
    #[pyo3(name = "BE")]
    fn be(&mut self, py: Python<'_>) -> PyResult<(Option<f64>, Option<f64>, Option<f64>)> {
        if self.bit(py)? != 0 { return Ok((Some(0.0), Some(0.0), Some(1.0))); }
        Ok((self.bd_(py)?, self.bd_(py)?, self.bd_(py)?))
    }
    #[pyo3(name = "BD3")]
    fn bd3(&mut self, py: Python<'_>) -> PyResult<(Option<f64>, Option<f64>, Option<f64>)> { Ok((self.bd_(py)?, self.bd_(py)?, self.bd_(py)?)) }
    #[pyo3(name = "RD2")]
    fn rd2(&mut self, py: Python<'_>) -> PyResult<(f64, f64)> { Ok((self.rd(py)?, self.rd(py)?)) }
    #[pyo3(name = "TV")]
    fn tv(&mut self, py: Python<'_>) -> PyResult<String> {
        let n = self.bs_(py)? as usize; let mut r = self.raw(py, n)?;
        while r.last() == Some(&0) { r.pop(); }
        Ok(r.iter().map(|&b| b as char).collect())
    }
    #[pyo3(name = "TU")]
    fn tu(&mut self, py: Python<'_>) -> PyResult<String> {
        let n = self.bs_(py)? as usize; let r = self.raw(py, 2 * n)?;
        let s: String = PyBytes::new_bound(py, &r).call_method1("decode", ("utf-16le", "replace"))?.extract()?;
        Ok(s.trim_end_matches('\0').to_string())
    }
    #[pyo3(name = "BLL")]
    fn bll(&mut self, py: Python<'_>) -> PyResult<u128> {
        let n = self.rbits(py, 3)? as usize;
        if n == 0 { return Ok(0); }
        let r = self.raw(py, n)?; let mut v: u128 = 0; for (k, b) in r.iter().enumerate() { v |= (*b as u128) << (8 * k); }
        Ok(v)
    }
}
