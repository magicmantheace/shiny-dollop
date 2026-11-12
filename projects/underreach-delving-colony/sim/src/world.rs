//! Voxel world: a bounded 3D grid of cells. `y` is depth (0 = top).
//! S1 models single-height carved spaces (rooms, shafts, tunnels) —
//! the sim's delvers occupy one cell each.

use serde::{Deserialize, Serialize};

#[derive(
    Clone, Copy, PartialEq, Eq, Hash, Debug, Serialize, Deserialize, PartialOrd, Ord,
)]
pub struct Pos {
    pub x: i32,
    pub y: i32,
    pub z: i32,
}

impl Pos {
    pub fn new(x: i32, y: i32, z: i32) -> Self {
        Self { x, y, z }
    }

    pub fn neighbors6(&self) -> [Pos; 6] {
        [
            Pos::new(self.x + 1, self.y, self.z),
            Pos::new(self.x - 1, self.y, self.z),
            Pos::new(self.x, self.y + 1, self.z),
            Pos::new(self.x, self.y - 1, self.z),
            Pos::new(self.x, self.y, self.z + 1),
            Pos::new(self.x, self.y, self.z - 1),
        ]
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum Cell {
    Earth,
    Stone,
    Ore,
    /// A fungal growth node in the Fungal Reaches — mined like ore,
    /// rendered into fungal oil instead.
    FungalNode,
    /// Cave-in-prone rock (S6 floor generation). Embedded in the
    /// rock by the floor generator as a hazard pocket. Generation
    /// and rendering only for now: the cave-in mechanics — and the
    /// timber-support answer — are a later slice, the same way S5
    /// modelled `flooded`/`hot` before simulating them.
    Loose,
    /// A bad-air pocket (S6 floor generation). Solid until carved;
    /// the bad-air mechanics and the ventilation answer are a
    /// later slice, like `Loose`.
    BadAir,
    Carved,
}

impl Cell {
    pub fn is_solid(&self) -> bool {
        !matches!(self, Cell::Carved)
    }
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct World {
    pub sx: usize,
    pub sy: usize,
    pub sz: usize,
    cells: Vec<Cell>,
}

impl World {
    pub fn new(sx: usize, sy: usize, sz: usize, fill: Cell) -> Self {
        Self {
            sx,
            sy,
            sz,
            cells: vec![fill; sx * sy * sz],
        }
    }

    pub fn volume(&self) -> usize {
        self.sx * self.sy * self.sz
    }

    pub fn idx(&self, p: Pos) -> Option<usize> {
        if p.x < 0 || p.y < 0 || p.z < 0 {
            return None;
        }
        let (x, y, z) = (p.x as usize, p.y as usize, p.z as usize);
        if x >= self.sx || y >= self.sy || z >= self.sz {
            return None;
        }
        Some((y * self.sz + z) * self.sx + x)
    }

    pub fn get(&self, p: Pos) -> Option<Cell> {
        self.idx(p).map(|i| self.cells[i])
    }

    pub fn set(&mut self, p: Pos, c: Cell) {
        if let Some(i) = self.idx(p) {
            self.cells[i] = c;
        }
    }

    /// Carve a solid cell into open space. Returns the material that was
    /// there, or `None` if the cell was already carved / out of bounds.
    pub fn carve(&mut self, p: Pos) -> Option<Cell> {
        let i = self.idx(p)?;
        let prev = self.cells[i];
        if prev == Cell::Carved {
            return None;
        }
        self.cells[i] = Cell::Carved;
        Some(prev)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn carve_returns_material_once() {
        let mut w = World::new(4, 4, 4, Cell::Stone);
        let p = Pos::new(1, 2, 1);
        assert_eq!(w.carve(p), Some(Cell::Stone));
        assert_eq!(w.get(p), Some(Cell::Carved));
        assert_eq!(w.carve(p), None);
    }

    #[test]
    fn out_of_bounds_is_rejected() {
        let mut w = World::new(4, 4, 4, Cell::Earth);
        assert_eq!(w.get(Pos::new(-1, 0, 0)), None);
        assert_eq!(w.get(Pos::new(4, 0, 0)), None);
        assert_eq!(w.carve(Pos::new(0, 99, 0)), None);
    }
}
