import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { countLabel, filterFolios, paginate } from '../src/lib/folio-list.ts';
import { folioRangeKeys } from '../src/lib/verses.ts';

const row = (folio, range) => ({
  folio,
  range,
  search: `${folio} ${range}`.toLowerCase(),
  ...folioRangeKeys(range),
});

const rows = [
  row('001B', 'Genesis 1:1 – Genesis 1:26'),
  row('002A', 'Genesis 1:26 – Genesis 2:19'),
  row('050A', 'Exodus 3:1 – Exodus 3:20'),
];

describe('filterFolios', () => {
  it('returns every row for an empty query', () => {
    assert.equal(filterFolios(rows, '  ').length, 3);
  });

  it('matches by folio text', () => {
    assert.deepEqual(filterFolios(rows, '002a').map((r) => r.folio), ['002A']);
  });

  it('matches by verse overlap', () => {
    assert.deepEqual(filterFolios(rows, 'Gen 1:26').map((r) => r.folio), ['001B', '002A']);
    assert.deepEqual(filterFolios(rows, 'Exod 3').map((r) => r.folio), ['050A']);
  });

  it('returns nothing for a verse no row covers', () => {
    assert.equal(filterFolios(rows, 'Ruth 1:1').length, 0);
  });
});

describe('paginate', () => {
  it('slices a full page', () => {
    assert.deepEqual(paginate(130, 2, 60), { page: 2, pages: 3, from: 60, to: 120 });
  });

  it('slices the last partial page', () => {
    assert.deepEqual(paginate(130, 3, 60), { page: 3, pages: 3, from: 120, to: 130 });
  });

  it('clamps out-of-range and invalid pages', () => {
    assert.equal(paginate(130, 9, 60).page, 3);
    assert.equal(paginate(130, 0, 60).page, 1);
    assert.equal(paginate(130, Number.NaN, 60).page, 1);
  });

  it('has one empty page when nothing matches', () => {
    assert.deepEqual(paginate(0, 1, 60), { page: 1, pages: 1, from: 0, to: 0 });
  });
});

describe('countLabel', () => {
  it('shows the visible range of all folios', () => {
    assert.equal(countLabel(paginate(259, 2, 60), 259, ''), '61–120 of 259 folios');
  });

  it('names the query when filtering', () => {
    assert.equal(countLabel(paginate(1, 1, 60), 1, ' 002a '), '1–1 of 1 folio matching “002a”');
  });

  it('reports no matches', () => {
    assert.equal(countLabel(paginate(0, 1, 60), 0, 'zzz'), 'No published folio matches “zzz”.');
  });
});
