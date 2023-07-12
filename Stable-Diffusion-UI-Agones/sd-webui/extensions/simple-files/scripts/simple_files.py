# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# The Simple File Manager for Stable diffusion webui.

import modules.scripts as scripts
import gradio as gr
import os
import sys
import shutil
import unicodedata
import zipfile
import tempfile

from modules import script_callbacks

def cjkcutlen(s, direction, width):
  w = 0
  if direction >= 0:
    for p, c in enumerate(s):
      w += 1 + (unicodedata.east_asian_width(c) in 'WF')
      if w + 1 > width:
        return s[0:p]
  else:
    for p, c in enumerate(reversed(s)):
      w += 1 + (unicodedata.east_asian_width(c) in 'WF')
      if w +1  > width:
        if p ==0:
          return ""
        return s[-p:]


def cjkwidth(s):
  return sum(1 + (unicodedata.east_asian_width(c) in 'WF') for c in s)

def normalize_de(de):

  if cjkwidth(de) > 32:
    t_de = cjkcutlen(de, 0, 25) + "..." + cjkcutlen(de, -1, 4)
  else:
    t_de = de

  norm = t_de + " "*(32 - cjkwidth(t_de) )
  return f"<pre>{norm}</pre>"

def mygetctime(base, de):
  f= os.path.join(base, de)
  try:
    return os.path.getctime(f)
  except FileNotFoundError:
    return os.stat(f, follow_symlinks=False)

def listdirentries(base, sortbytime, reverse):
  de_all = os.listdir(base)
  dirs = [x for x in de_all if os.path.isdir(os.path.join(base, x))]
  files = [x for x in de_all if not os.path.isdir(os.path.join(base, x))]
  if sortbytime:
    dirs.sort(key=lambda x: mygetctime(base, x), reverse=reverse)
  else:
    dirs.sort(reverse=reverse)
  return dirs + files

initcwd = os.path.realpath(os.path.curdir)

def on_ui_tabs():
  with gr.Blocks(analytics_enabled=False) as ui_component:

    cde = gr.State(["."])
    selected_files = gr.State([])

    history = gr.State(["PLACEHOLDER"])

    with gr.Row():
      cwd = gr.Textbox(initcwd, label="Dir", elem_id="simple_fb_path")
      upload = gr.Files(file_count="multiple")
    with gr.Row():
      with gr.Column(scale=2):
        with gr.Row():
          navi_back = gr.Button(label="Back", value="Back")
          navi_forward = gr.Button(label="Forward", value="Forward")
        with gr.Row():
          sortbytime = gr.Checkbox(label="Sort By Time")
          reverse = gr.Checkbox(label="Reverse")
        with gr.Row():
          fm = gr.Dataset(components=[gr.HTML(visible=False)], samples=[[normalize_de("./")]], type="index", label="")
      with gr.Column(scale=1):
        with gr.Row():
          finfo = gr.Files(value=None, interactive=False, visible=True)
        with gr.Row():
          clear_selected = gr.Button(value="Clear")
        with gr.Row():
          zip_file_name = gr.Textbox(value = "all.zip", label="Generate Zip Filename:", interactive=True)
          gen_zip_button = gr.Button(value="Generate Zip")
        with gr.Row():
          download_file = gr.File(value=None, interactive=False, visible=True)

    def goto_with_hist(hist, path, selected, sortbytime, reverse):
      gt = gotodir(path, selected, sortbytime, reverse)
      *_, new_path = gt
      if hist[0] == new_path:
        new_hist = hist
      else:
        new_hist = [new_path] + hist
      return new_hist, *gt

    def hist_back_forward(button, hist, path, selected, sortbytime, reverse):
      if button == "Forward":
        if hist[-1] == "PLACEHOLDER":
          return hist, *gotodir(path, selected, sortbytime, reverse)
        new_hist = [hist[-1]] + hist[0:-1]
        new_path = new_hist[0]
      else:
        if len(hist) <= 1 or hist[1] == "PLACEHOLDER":
          return hist, *gotodir(path, selected, sortbytime, reverse)
        new_hist = hist[1:]+[hist[0]]
        new_path = new_hist[0]
      return new_hist, *gotodir(new_path, selected, sortbytime, reverse)

    def gotodir(path, selected, sortbytime, reverse):
      if os.path.isdir(path):
        c = [x for x in listdirentries(path, sortbytime, reverse)]
        f_info = None
        newpath = path
      else:
        newpath = os.path.dirname(path)
        c = [x for x in listdirentries(newpath, sortbytime, reverse)]
        if path in selected:
          selected.remove(path)
          f_info = selected
        else:
          f_info = selected + [path]

      new_selected = selected if f_info is None else f_info

      contents = [[normalize_de("../")]]
      for x in c:
        if os.path.isdir(os.path.join(newpath, x)):
          contents.append([normalize_de(f"{x}/")])
        else:
          contents.append([normalize_de(x)])
      return contents, [".."] + c, new_selected, f_info, newpath

    def fm_click(history, dir_entry, cde, cwd, selected, sortbytime, reverse):
      tmp_cwd = os.path.realpath(os.path.join(cwd, cde[dir_entry]))
      return goto_with_hist(history, tmp_cwd, selected, sortbytime, reverse)


    def process_zip(f, zip_file_name):
      commonbase = os.path.commonpath(f)
      tmpzipname = os.path.join("/tmp", zip_file_name)
      with zipfile.ZipFile(tmpzipname, "x") as z:
        for i in f:
          with z.open(i.replace(commonbase, "", 1), "w") as dst:
            with open(i, "rb") as src:
              shutil.copyfileobj(src, dst)

      return tmpzipname

    def process_upload(fl, cwd, sl, sortbytime, reverse):
      for f in fl:
        filename = os.path.basename(f.name)
        targetfn = os.path.join(cwd, filename)
        shutil.copyfile(f.name, targetfn)
      return gotodir(cwd, [], sortbytime, reverse)

    output_group = [fm, cde, selected_files, finfo, cwd]
    input_group = [cwd, selected_files, sortbytime, reverse]
    cwd.submit(goto_with_hist,
               inputs=[history] + input_group,
               outputs=[history] + output_group)

    navi_back.click(hist_back_forward,
                    inputs=[navi_back, history] + input_group,
                    outputs=[history] + output_group)
    navi_forward.click(hist_back_forward,
                    inputs=[navi_forward, history] + input_group,
                    outputs=[history] + output_group)

    fm.click(fm_click,
             inputs=[history, fm, cde] + input_group,
             outputs=[history] + output_group)
    upload.upload(process_upload,
                  inputs=[upload] + input_group,
                  outputs=output_group)
    sortbytime.change(gotodir,
                      inputs=input_group,
                      outputs=output_group)
    reverse.change(gotodir,
                   inputs=input_group,
                   outputs=output_group)
    clear_selected.click(fn = lambda: ([], []), outputs=[selected_files, finfo])
    zip_file_name.submit(fn = process_zip,
                         inputs=[selected_files, zip_file_name],
                         outputs=[download_file])
    gen_zip_button.click(fn = process_zip,
                         inputs=[selected_files, zip_file_name],
                         outputs=[download_file])
    return [(ui_component, "Simple File Manager", "simple_fm_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
