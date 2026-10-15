//! Dependency-free exact five-slot search. Input features are prepared in Python.
use std::io::{self, Read};
use std::str::FromStr;

fn take<T: FromStr>(it: &mut std::str::SplitWhitespace<'_>) -> T {
    it.next().expect("missing protocol field").parse().ok().expect("invalid protocol field")
}

// Python round(x, 4) rounds the actual binary value, not x*10000's half.
// Outside a conservative multiplication-error interval the fast result is exact;
// ambiguous halves use Rust's exact, ties-even decimal formatting.
fn round4(x: f64) -> f64 {
    let scaled = x * 10000.0;
    let distance = (scaled.abs().fract() - 0.5).abs();
    if distance <= scaled.abs() * f64::EPSILON * 2.0 + f64::EPSILON {
        format!("{x:.4}").parse().unwrap()
    } else {
        scaled.round() / 10000.0
    }
}

#[derive(Clone, Copy, Default)]
struct Sum { hi: f64, lo: f64 }
impl Sum {
    fn add(&mut self, x: f64, compensated: bool) {
        if compensated {
            let t = self.hi + x;
            self.lo += if self.hi.abs() >= x.abs() { (self.hi - t) + x } else { (x - t) + self.hi };
            self.hi = t;
        } else { self.hi += x; }
    }
    fn value(self) -> f64 { self.hi + self.lo }
}

struct Member {
    weak: u64, resist: u64, hit: u64, coverage: [f64; 18], overlap: Vec<u32>,
    quality: f64, evolution: i64, additions: i64, favorite: i64, name: usize,
    conflicts: Vec<u64>,
}
#[derive(Clone, Copy, Default)]
struct State {
    weak: u64, resist: u64, ones: u64, twos: u64, fours: u64, hit: u64,
    overlap: u32, quality: Sum, evolution: i64, additions: i64, favorites: i64,
}
impl State {
    fn add(mut self, member: &Member, chosen: &[usize], compensated: bool) -> Self {
        self.weak |= member.weak;
        self.resist |= member.resist;
        let one = self.ones & member.weak;
        self.ones ^= member.weak;
        let two = self.twos & one;
        self.twos ^= one;
        self.fours ^= two;
        self.hit |= member.hit;
        for &i in chosen { self.overlap += member.overlap[i]; }
        self.quality.add(member.quality, compensated);
        self.evolution += member.evolution;
        self.additions += member.additions;
        self.favorites += member.favorite;
        self
    }
}
struct Winner { indices: [usize; 5], synergy: f64, core: f64, full: f64, quality: f64,
                evolution: i64, additions: i64, favorites: i64, names: [usize; 5] }
// Only immutable suffix features and ownership masks; candidate visit order is unchanged.
struct Pruning {
    quality: Vec<[f64; 2]>, absmax: Vec<f64>, additions: Vec<[i64; 2]>, incoming: Vec<Vec<u64>>,
}
impl Pruning {
    fn new(members: &[Member], n: usize, category: &str) -> Option<Self> {
        match category {
            "Best" if members[..n].iter().all(|m| m.quality.is_finite() && m.quality.abs() <= 1e8) => (),
            "Pokedex" if members[..n].iter().all(|m| (0..=((1_i64 << 53) - 1) / 5).contains(&m.additions)) => (),
            _ => return None,
        }
        let mut quality = vec![[f64::NEG_INFINITY; 2]; n + 1];
        let mut absmax = vec![0.0_f64; n + 1];
        for i in (0..n).rev() {
            let [a, b] = quality[i + 1]; let v = members[i].quality;
            quality[i] = if v >= a { [v, a] } else { [a, b.max(v)] };
            absmax[i] = absmax[i + 1].max(v.abs());
        }
        let mut additions = if category == "Pokedex" { vec![[0_i64; 2]; n + 1] } else { vec![] };
        if !additions.is_empty() {
            for i in (0..n).rev() {
                let [a, b] = additions[i + 1]; let v = members[i].additions;
                additions[i] = if v >= a { [v, a] } else { [a, b.max(v)] };
            }
        }
        // Incoming[i] lists candidates j whose own row conflicts with earlier i.
        // This also preserves the old traversal on non-symmetric wire matrices.
        let mut incoming = vec![vec![0_u64; n.div_ceil(64)]; n];
        for (j, member) in members[..n].iter().enumerate() {
            for (i, row) in incoming.iter_mut().enumerate() {
                if member.conflicts[i / 64] & (1 << (i % 64)) != 0 { row[j / 64] |= 1 << (j % 64); }
            }
        }
        Some(Self { quality, absmax, additions, incoming })
    }
    fn strictly_below(&self, members: &[Member], start: usize, chosen: &[usize], state: State, best: &Winner) -> bool {
        let remaining = 5 - chosen.len();
        if !self.additions.is_empty() {
            let upper = state.additions + self.additions[start][..remaining].iter().sum::<i64>();
            return upper < best.additions;
        }
        let mut upper = 0.0_f64; let mut magnitude = 0.0_f64;
        for &i in chosen {
            upper = (upper + members[i].quality).next_up();
            magnitude = (magnitude + members[i].quality.abs()).next_up();
        }
        for k in 0..remaining {
            upper = (upper + self.quality[start][k]).next_up();
            magnitude = (magnitude + self.absmax[start]).next_up();
        }
        // For five terms, |hi|,|t|<2S, |d|<5S, |e|<7S, |lo|<36S.
        // Neumaier's t error cancels in hi'+lo'; the remaining errors plus
        // final value() are <=303*u*S+16*eta <256*EPSILON*S, S>=1.
        // See the numerical proof in docs/primary-subtree-bounds.md.
        let error = (256.0 * f64::EPSILON * magnitude.max(1.0)).next_up();
        let mean = ((upper + error).next_up() / 5.0).next_up();
        mean.is_finite() && round4(mean) < best.quality
    }
    fn completions(&self, start: usize, chosen: &[usize], n: usize) -> u64 {
        let words = n.div_ceil(64);
        let mut allowed = vec![0_u64; words];
        for (w, mask) in allowed.iter_mut().enumerate() {
            if w < start / 64 { continue; }
            *mask = if w == start / 64 { u64::MAX << (start % 64) } else { u64::MAX };
            if w == words - 1 && n % 64 != 0 { *mask &= (1 << (n % 64)) - 1; }
            for &i in chosen { *mask &= !self.incoming[i][w]; }
        }
        if chosen.len() == 4 { return allowed.iter().map(|v| v.count_ones() as u64).sum(); }
        let mut count = 0;
        for (w, &mask) in allowed.iter().enumerate() {
            let mut bits = mask;
            while bits != 0 {
                let bit = bits.trailing_zeros(); let i = w * 64 + bit as usize;
                bits &= bits - 1;
                for (later_word, &later) in allowed.iter().enumerate().skip(w) {
                    let mut compatible = later & !self.incoming[i][later_word];
                    if later_word == w { compatible &= u64::MAX.checked_shl(bit + 1).unwrap_or(0); }
                    count += compatible.count_ones() as u64;
                }
            }
        }
        count
    }
}

struct Search {
    members: Vec<Member>, n: usize, category: String, compensated: bool,
    uniform: bool, strength: f64, disjoint: bool,
    independent: u64, scored: u64, primary_skips: u64, best: Option<Winner>,
    pruning: Option<Pruning>, pruned_subtrees: u64, subtree_completions: u64,
}
impl Search {
    fn score(&self, state: State, indices: &[usize]) -> f64 {
        let coverage = if self.uniform {
            state.hit.count_ones() as f64 * self.strength / 18.0
        } else {
            let mut total = Sum::default();
            for column in 0..18 {
                let mut best: f64 = 0.0;
                for &i in indices { best = best.max(self.members[i].coverage[column]); }
                total.add(best, self.compensated);
            }
            total.value() / 18.0
        };
        let covered = if self.disjoint { state.weak & state.resist } else {
            let mut covered = 0;
            for &i in indices {
                let mut other_resist = 0;
                for &j in indices { if i != j { other_resist |= self.members[j].resist; } }
                covered |= self.members[i].weak & other_resist;
            }
            covered
        };
        let defence = if state.weak == 0 { 1.0 } else { covered.count_ones() as f64 / state.weak.count_ones() as f64 };
        let worst = if state.fours & state.twos != 0 { 6 } else if state.fours & state.ones != 0 { 5 }
            else if state.fours != 0 { 4 } else if state.twos & state.ones != 0 { 3 }
            else if state.twos != 0 { 2 } else if state.ones != 0 { 1 } else { 0 };
        let size = indices.len() as f64;
        round4(4.0 * coverage + 2.5 * defence - 1.5 * state.overlap as f64 / size
               - 1.5 * (worst - 2).max(0) as f64 / size)
    }
    fn better(&self, a: &Winner, b: &Winner) -> bool {
        let af = match self.category.as_str() {
            "Best" => [a.quality, a.synergy, a.favorites as f64, 0.0],
            "Pokedex" => [a.additions as f64, a.synergy, a.quality, a.favorites as f64],
            _ => [a.synergy, a.evolution as f64, a.quality, a.favorites as f64],
        };
        let bf = match self.category.as_str() {
            "Best" => [b.quality, b.synergy, b.favorites as f64, 0.0],
            "Pokedex" => [b.additions as f64, b.synergy, b.quality, b.favorites as f64],
            _ => [b.synergy, b.evolution as f64, b.quality, b.favorites as f64],
        };
        for (x, y) in af.into_iter().zip(bf) {
            if x != y { return x > y; }
        }
        a.names < b.names
    }
    fn visit(&mut self, start: usize, depth: usize, chosen: &mut [usize; 6], state: State) {
        if depth == 5 {
            self.independent += 1;
            let quality = round4(state.quality.value() / 5.0);
            if let Some(best) = &self.best {
                if (self.category == "Best" && quality < best.quality)
                    || (self.category == "Pokedex" && state.additions < best.additions) {
                    self.primary_skips += 1;
                    return;
                }
            }
            self.scored += 1;
            let core = self.score(state, &chosen[..5]);
            let full_state = state.add(&self.members[self.n], &chosen[..5], self.compensated);
            chosen[5] = self.n;
            let full = self.score(full_state, chosen);
            let synergy = round4(0.65 * core + 0.35 * full);
            let mut names = [0; 5];
            for i in 0..5 { names[i] = self.members[chosen[i]].name; }
            names.sort_unstable();
            let candidate = Winner { indices: chosen[..5].try_into().unwrap(), synergy, core, full,
                quality, evolution: state.evolution, additions: state.additions, favorites: state.favorites, names };
            if self.best.as_ref().is_none_or(|best| self.better(&candidate, best)) { self.best = Some(candidate); }
            return;
        }
        if self.n < 5 - depth || start > self.n - (5 - depth) { return; }
        if depth >= 3 {
            if let (Some(pruning), Some(best)) = (&self.pruning, &self.best) {
                if pruning.strictly_below(&self.members, start, &chosen[..depth], state, best) {
                    let count = pruning.completions(start, &chosen[..depth], self.n);
                    self.independent += count; self.primary_skips += count;
                    self.pruned_subtrees += 1; self.subtree_completions += count;
                    return;
                }
            }
        }
        for i in start..=self.n - (5 - depth) {
            if chosen[..depth].iter().any(|&j| self.members[i].conflicts[j / 64] & (1 << (j % 64)) != 0) { continue; }
            let next = state.add(&self.members[i], &chosen[..depth], self.compensated);
            chosen[depth] = i;
            self.visit(i + 1, depth + 1, chosen, next);
        }
    }
}
fn main() {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap();
    if std::env::args().nth(1).as_deref() == Some("--round4") {
        let rounded: Vec<String> = input.split_whitespace()
            .map(|v| round4(v.parse().unwrap()).to_string()).collect();
        println!("[{}]", rounded.join(","));
        return;
    }
    let mut it = input.split_whitespace();
    assert_eq!(take::<u32>(&mut it), 1);
    let n = take(&mut it);
    let category = take::<String>(&mut it);
    let compensated = take::<u32>(&mut it) != 0;
    let uniform = take::<u32>(&mut it) != 0;
    let strength = take(&mut it);
    let disjoint = take::<u32>(&mut it) != 0;
    let mut members = Vec::new();
    for _ in 0..=n {
        let weak = take(&mut it); let resist = take(&mut it); let hit = take(&mut it);
        let mut coverage = [0.0; 18];
        for v in &mut coverage { *v = take(&mut it); }
        let overlap = (0..=n).map(|_| take(&mut it)).collect();
        members.push(Member { weak, resist, hit, coverage, overlap,
            quality: 0.0, evolution: 0, additions: 0, favorite: 0, name: 0, conflicts: vec![] });
    }
    for m in members.iter_mut().take(n) {
        m.quality = take(&mut it); m.evolution = take(&mut it); m.additions = take(&mut it);
        m.favorite = take(&mut it); m.name = take(&mut it);
        m.conflicts = (0..n.div_ceil(64)).map(|_| take(&mut it)).collect();
    }
    assert!(it.next().is_none(), "extra protocol fields");
    let pruning = Pruning::new(&members, n, &category);
    let mut search = Search { members, n, category, compensated, uniform, strength, disjoint,
        independent: 0, scored: 0, primary_skips: 0, best: None, pruning,
        pruned_subtrees: 0, subtree_completions: 0 };
    search.visit(0, 0, &mut [0; 6], State::default());
    let winner = match search.best {
        Some(w) => format!("\"indices\":{:?},\"synergy\":{},\"core\":{},\"full\":{},\"quality\":{}",
                           w.indices, w.synergy, w.core, w.full, w.quality),
        None => "\"indices\":null".to_string(),
    };
    println!("{{\"protocol\":1,{},\"independent_combinations\":{},\"scored_combinations\":{},\"primary_skips\":{}}}",
             winner, search.independent, search.scored, search.primary_skips);
    if std::env::args().any(|arg| arg == "--pruning-stats") {
        eprintln!("{{\"pruned_subtrees\":{},\"leaf_visits\":{},\"subtree_completions\":{}}}",
                  search.pruned_subtrees, search.independent - search.subtree_completions, search.subtree_completions);
    }
}
