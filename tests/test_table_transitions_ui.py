# Copyright 2026 3LC Inc.
# SPDX-License-Identifier: Apache-2.0
"""Table identity and labels follow the latest input, including preset/Undo metadata reuse."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_table_resolution(tmp_path):
    ui = (Path(__file__).parents[1] / "src/tlc_plugin_sam3/ui.html").read_text()
    start = ui.index("function sam3ReadTable(")
    end = re.search(r"^}\n", ui[start:], re.MULTILINE)
    assert end
    source = ui[start : start + end.end()]
    script = tmp_path / "table-reader.js"
    script.write_text(
        r"""
const assert = require('node:assert/strict');
const elements = {};
const document = {getElementById: id => elements[id] ||= {value:''}};
let url='a', tableMode=true, pending=[], calls=0, resolved=[];
let _sam3TableRead=0, _sam3TableLoading=false, _sam3TableError='', _sam3Labels=[], _sam3ColorIndex=0;
const _sam3Val=()=>url, _sam3IsTable=()=>tableMode, sam3Gate=()=>{}, sam3Log=()=>{};
const sam3RenderLabels=()=>{}, _sam3NextColor=()=>'blue';
const sam3Presets={tableResolved:async (url,info)=>{resolved.push({url,info}); return false;}};
const _sam3Post=()=>{calls++; return new Promise(r=>pending.push(r));};
"""
        + source
        + r"""
(async()=>{
  const first=sam3ReadTable(false);
  url='b'; const second=sam3ReadTable(false);
  url='a'; const last=sam3ReadTable(false);
  pending[2]({project_name:'A', labels:['new'], modality:'segmentation'}); await last;
  pending[0]({project_name:'old A', labels:['old']}); pending[1]({project_name:'B',labels:['wrong']});
  await Promise.all([first,second]);
  assert.equal(resolved.length,1); assert.equal(_sam3Labels[0].name,'new');
  // Cached metadata from reset or Undo needs no second lookup; saved labels/output remain intact.
  document.getElementById('sam3-project-name').value='custom output';
  await sam3ReadTable(false,{url:'a',info:{project_name:'A',labels:['other']}});
  assert.equal(calls,3); assert.equal(_sam3Labels[0].name,'new');
  assert.equal(document.getElementById('sam3-project-name').value,'custom output');
  // After defaults clear labels, populate the new table's labels.
  _sam3Labels=[];
  await sam3ReadTable(false,{url:'a',info:{project_name:'A',labels:['fresh']}});
  assert.equal(_sam3Labels[0].name,'fresh'); assert.equal(_sam3TableLoading,false);
  // Unreadable inputs block action instead of being mistaken for an empty schema.
  const failed=sam3ReadTable(false); pending[3]({error:'unreadable table'}); await failed;
  assert.match(_sam3TableError,/unreadable table/); assert.equal(_sam3TableLoading,false);
  assert.equal(_sam3Labels[0].name,'fresh');
  tableMode=false; await sam3ReadTable(false); assert.equal(calls,4);
})().catch(e=>{console.error(e); process.exitCode=1;});
"""
    )
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
