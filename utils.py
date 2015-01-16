
import os
import json
import os.path
import datetime
import collections

import sublime
import sublime_plugin


class UtilsEditViewCommand(sublime_plugin.TextCommand):
    def run(self, edit, data=None, start=0, end=None):
        start = int(start)
        if end is not None:
            end = int(end)
        was_read_only = self.view.is_read_only()
        if was_read_only:
            self.view.set_read_only(False)
        if end is not None and not start == end:
            if data is not None:
                self.view.replace(edit, sublime.Region(start, end), data)
            else:
                self.view.erase(edit, sublime.Region(start, end))
        elif data is not None:
            self.view.insert(edit, start, data)
        if was_read_only:
            self.view.set_read_only(True)


class UtilsInsertTimeStampCommand(sublime_plugin.TextCommand):
    def run(self, edit, format='%Y-%m-%d %H:%M:%S'):
        settings = sublime.load_settings('Utils.sublime-settings')
        stamp_format = settings.get('stamp_format', format)
        sel = self.view.sel()
        if sel:
            region = sel[0]
            self.view.run_command(
                'utils_edit_view',
                {
                    'data': datetime.datetime.now().strftime(stamp_format),
                    'start': region.begin(),
                    'end': region.end()
                }
            )


class UtilsOpenPluginFileCommand(sublime_plugin.WindowCommand):
    def run(self, path_so_far=''):
        # Direct to here again if no path_so_far
        on_done = self.on_done if path_so_far else self.run
        # Set instance path_so_far to selection if int, else provided path_so_far
        self.path_so_far = self.files[path_so_far] if isinstance(path_so_far, int) else path_so_far
        # Get the list for the instance path_so_far
        cur_directory = os.path.join(sublime.packages_path(), self.path_so_far)
        directory = os.listdir(cur_directory)
        # If we are not at the top Packages Directory add a ..
        if not os.path.abspath(cur_directory) == sublime.packages_path():
            directory.insert(0, '..')
        directory = [x for x in directory if not x.endswith('.pyc')]
        # append a forward slash to all directories
        directory = [
            x + '/' if os.path.isdir(os.path.join(cur_directory, x)) else x
            for x in directory
        ]
        self.files = sorted(directory)
        # Prompt the user
        sublime.set_timeout_async(
            lambda: self.window.show_quick_panel(self.files, on_done, 0, -1, None),
            0
        )

    def on_done(self, selection):
        if selection != -1:
            # Get the newly selected path
            sub_path = os.path.join(
                self.path_so_far,
                self.files[selection]
            )
            # Get the full newly selected path
            path = os.path.join(
                sublime.packages_path(),
                sub_path
            )
            # Reset the options
            self.files = self.path_so_far = None
            # Decide on what action to take:
            if os.path.isdir(path):
                self.run(sub_path)
            else:
                self.window.open_file(path)


class UtilsReloadViewCommand(sublime_plugin.WindowCommand):
    def run(self, all=False):
        # Reload all views or current view
        if all:
            log('Reloading all views')
            views = self.window.views()
        else:
            log('Reloading current view')
            views = [self.window.active_view()]

        # Keep track of starting active views and group
        active_group = self.window.active_group()
        active_views = [
            self.window.active_view_in_group(g) for g in range(self.window.num_groups())
        ]

        for view in views:
            group, index = self.window.get_view_index(view)

            file_name = view.file_name()
            if not file_name:
                log('Not reloading "%s"' % view.name())
                continue

            log('Reloading "%s"' % file_name)

            is_active_view = False
            if view in active_views:
                is_active_view = True
                del active_views[active_views.index(view)]

            sel = view.sel()
            if sel:
                location = ''.join([':%d' % (x + 1) for x in view.rowcol(sel[0].begin())])
                file_name += location

            self.window.focus_view(view)
            self.window.run_command('close')
            self.window.open_file(file_name, sublime.ENCODED_POSITION)
            view = self.window.active_view()
            self.window.set_view_index(view, group, index)

            if is_active_view:
                active_views.append(view)

        for view in active_views:
            self.window.focus_view(view)
        self.window.focus_group(active_group)


class UtilsSetViewNameCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.window().show_input_panel('Name', '', self.on_done, None, None)

    def on_done(self, name):
        self.view.set_name(name)


class UtilsPythonToJsonCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        regions = get_selections(self.view, expand_line=False, expand_all=True)
        for region in regions:
            content = self.view.substr(region)
            content = python_2_json(content)
            content = json.dumps(content)
            self.view.run_command(
                'utils_edit_view',
                {
                    'data': content,
                    'start': region.begin(),
                    'end': region.end()
                }
            )


class UtilsTidyJsonCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        for region in get_selections(self.view):
            data = self.view.substr(region)
            data = json.loads(data, object_pairs_hook=collections.OrderedDict)
            data = json.dumps(data, indent=4)
            self.view.replace(edit, region, data)


class UtilsColumnsIndentCommand(sublime_plugin.TextCommand):
    # maybe extend this to read in using csvreader.
    def run(self, edit, separator=None, replacement=None):
        if separator is None:
            self.view.window().show_input_panel(
                'separator',
                '',
                lambda x: self.on_done('separator', x, {}),
                None,
                None
            )
        elif replacement is None:
            self.view.window().show_input_panel(
                'replacement',
                separator.replace('\\', '\\\\').replace('\n', '\\n').replace('\t', '\\t'),
                lambda x: self.on_done('replacement', x, {'separator': separator}),
                None,
                None
            )
        else:
            selection = get_selections(self.view)
            selection = reversed(list(selection))

            for region in selection:
                region = self.view.line(region)
                region_start_line = self.view.rowcol(region.begin())[0]
                content = self.view.substr(region)
                lines = content.split('\n')
                lines_bits = [x.strip().split(separator) for x in lines]
                bit_widths = []
                for line_bits in lines_bits:
                    for i, line_bit in enumerate(line_bits):
                        if len(bit_widths) <= i:
                            bit_widths.append(0)
                        bit_widths[i] = max(bit_widths[i], len(line_bit.strip()))
                for i, line_bits in enumerate(lines_bits):
                    line = replacement.join(
                        [
                            b.strip().ljust(bit_widths[j])
                            for j, b in enumerate(line_bits)
                        ]
                    )
                    line_region = self.view.line(self.view.text_point(i + region_start_line, 0))
                    self.view.replace(edit, line_region, line)

    def on_done(self, name, value, values):
        i = 0
        while i < len(value) - 1:
            c0 = value[i]
            c1 = value[i + 1]
            if c0 == '\\' and c1 in ['t', 'n', '\\']:
                c2 = {'t': '\t', 'n': '\n', '\\': '\\'}[c1]
                value = value[:i] + c2 + value[i + 2:]
                i = i + 1
            i = i + 1
        values[name] = value
        self.view.run_command('utils_columns_indent', values)


########################################################
# START Helpers
########################################################

def log(msg, area='Utils', debug=False):
    settings = sublime.load_settings('Utils.sublime-settings')
    if settings.get('debug', debug):
        if callable(msg):
            msg = msg()
        print('[%s]: %s' % (area, str(msg)))


def get_selections(view, expand_line=False, expand_all=True):
    regions = list(view.sel())
    if len(regions) == 0 and expand_all:
        regions.append(sublime.Region(0, view.size()))
    elif len(regions) == 1:
        if regions[0].empty():
            if expand_line and not expand_all:
                regions[0] = view.line(regions[0].a)
            elif expand_all:
                regions[0] = sublime.Region(0, view.size())
    regions = [x for x in regions if not x.empty()]
    return regions


def python_2_json(data):
    def __add_value(parent, value):
        if isinstance(parent['value'], dict):
            if 'current_key' not in parent:
                parent['current_key'] = value
            else:
                parent['value'][parent['current_key']] = value
                del parent['current_key']
        elif isinstance(parent['value'], list):
            parent['value'].append(value)
    root = []
    current = {'value': root}
    i = 0
    opener = ''
    last_i = -1
    while i < len(data):
        char = data[i]
        if last_i >= i:
            break
        last_i = i
        if char in ['[', '(']:
            value = []
            __add_value(current, value)
            current = {'value': value, 'parent': current}
        elif char == '{':
            value = collections.OrderedDict()
            __add_value(current, value)
            current = {'value': value, 'parent': current}
        elif char in ['"', "'"]:
            value = ""
            opener = char
            if data[i: i + 3] == char + char + char:
                i += 2
                opener = char + char + char
            i += 1
            char = data[i]
            while data[i: i + len(opener)] != opener:
                value += char
                i += 1
                char = data[i]
                if char == '\\':
                    i += 1
                    value += data[i: i + 1]
            if len(opener) > 1:
                i += 2
            __add_value(current, value)
        elif char == 'N':
            __add_value(current, None)
            i += 3
        elif char == 'T':
            __add_value(current, True)
            i += 3
        elif char == 'F':
            __add_value(current, False)
            i += 4
        elif char.isdigit() or char == '.':
            value = char
            i += 1
            char = data[i]
            while char in '0123456789.':
                value += char
                i += 1
                char = data[i]
            __add_value(current, value)
        elif char in [']', '}', ')']:
            current = current['parent']
        i += 1
    return root[0]


########################################################
# End Helpers
########################################################
