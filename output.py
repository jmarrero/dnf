#!/usr/bin/python -t

"""This handles actual output from the cli"""

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
# Copyright 2004 Duke University 

import os
import os.path
import sys
import time
from i18n import _
import libxml2

import yum.Errors

class YumOutput:

    def printtime(self):
        return time.strftime('%b %d %H:%M:%S', time.localtime(time.time()))
        
    
    def failureReport(self, msg, errorlog=None, relative=None):
        """failure output for failovers from urlgrabber"""
        
        if errorlog:
            errorlog(1, '%s: %s' % (relative, msg))
        raise msg
    
        
    def simpleProgressBar(self, current, total, name=None):
        """simple progress bar 50 # marks"""
        
        mark = '#'
        if not sys.stdout.isatty():
            return
            
        if current == 0:
            percent = 0 
        else:
            if total != 0:
                percent = current*100/total
            else:
                percent = 0
    
        numblocks = int(percent/2)
        hashbar = mark * numblocks
        if name is None:
            output = '\r%-50s %d/%d' % (hashbar, current, total)
        else:
            output = '\r%-10.10s: %-50s %d/%d' % (name, hashbar, current, total)
         
        if current <= total:
            sys.stdout.write(output)
    
        if current == total:
            sys.stdout.write('\n')
    
        sys.stdout.flush()
        
    
    def simpleList(self, pkg):
        n = pkg.name
        a = pkg.arch
        e = pkg.epoch
        v = pkg.version
        r = pkg.release
        repo = pkg.returnSimple('repoid')
        if e != '0':
            ver = '%s:%s-%s' % (e, v, r)
        else:
            ver = '%s-%s' % (v, r)
        
        print "%-36s%-7s%-25s%-12s" % (n, a, ver, repo)
    
    
    def infoOutput(self, pkg):
        print _("Name   : %s") % pkg.name
        print _("Arch   : %s") % pkg.arch
        print _("Version: %s") % pkg.version
        print _("Release: %s") % pkg.release
        print _("Size   : %s") % format_number(float(pkg.size()))
        print _("Repo   : %s") % pkg.returnSimple('repoid')
        print _("Summary: %s") % pkg.returnSimple('summary')
        print _("Description:\n %s") % pkg.returnSimple('description')
        print ""
    
        
    def listPkgs(self, lst, description, outputType):
        """outputs based on whatever outputType is. Current options:
           'list' - simple pkg list
           'info' - similar to rpm -qi output
           'rss' - rss feed-type output"""
        
        if outputType in ['list', 'info']:
            thingslisted = 0
            if len(lst) > 0:
                thingslisted = 1
                print '%s' % description
                lst.sort(self.sortPkgObj)
                for pkg in lst:
                    if outputType == 'list':
                        self.simpleList(pkg)
                    elif outputType == 'info':
                        self.infoOutput(pkg)
                    else:
                        pass
    
            if thingslisted == 0:
                return 1, ['No Packages to list']
        
        elif outputType == 'rss':
            # take recent updates only and dump to an rss compat output
    
            if self.conf.getConfigOption('rss-filename') is None:
                raise yum.Errors.YumBaseError, \
                   "No File specified for rss create"
            else:
                fn = self.conf.getConfigOption('rss-filename')

            if fn[0] != '/':
                cwd = os.getcwd()
                fn = os.path.join(cwd, fn)
            try:
                fo = open(fn, 'w')
            except IOError, e:
                raise yum.Errors.YumBaseError, \
                   "Could not open file %s for rss create" % (e)
    
            if len(lst) > 0:
                doc = libxml2.newDoc('1.0')
                self.xmlescape = doc.encodeEntitiesReentrant
                rss = doc.newChild(None, 'rss', None)
                rss.setProp('version', '2.0')
                node = rss.newChild(None, 'channel', None)
                rssheader = self.startRSS()
                fo.write(rssheader)
                for pkg in lst:
                    item = self.rssnode(node, pkg)
                    fo.write(item.serialize("utf-8", 1))
                    item.unlinkNode()
                    item.freeNode()
                    del item
                
                end = self.endRSS()
                fo.write(end)
                fo.close()
                del fo
                doc.freeDoc()
                del doc
    
    def startRSS(self):
        """return string representation of rss preamble"""
    
        rfc822_format = "%a, %d %b %Y %X GMT"
        now = time.strftime(rfc822_format, time.gmtime())
        rssheader = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <title>Yum Package List</title>
        <link>http://linux.duke.edu/projects/yum/</link>
        <description>Yum Package List</description>
        <pubDate>%s</pubDate>
        <generator>Yum</generator>
        """ % now
        
        return rssheader
    
    def rssnode(self, node, pkg):
        """return an rss20 compliant item node
           takes a node, and a pkg object"""
        
        repo = self.repos.getRepo(pkg.repoid)
        url = repo.urls[0]
        rfc822_format = "%a, %d %b %Y %X GMT"
        clog_format = "%a, %d %b %Y GMT"
        xhtml_ns = "http://www.w3.org/1999/xhtml"
        escape = self.xmlescape
        
        item = node.newChild(None, 'item', None)
        title = escape(str(pkg))
        item.newChild(None, 'title', title)
        date = time.gmtime(float(pkg.returnSimple('buildtime')))
        item.newChild(None, 'pubDate', time.strftime(rfc822_format, date))
        item.newChild(None, 'guid', pkg.returnSimple('id'))
        link = url + '/' + pkg.returnSimple('relativepath')
        item.newChild(None, 'link', escape(link))

        # build up changelog
        changelog = ''
        cnt = 0
        for e in pkg.changelog:
            cnt += 1
            if cnt > 3: 
                changelog += '...'
                break
            (date, author, desc) = e
            date = time.strftime(clog_format, time.gmtime(float(date)))
            changelog += '%s - %s\n%s\n\n' % (date, author, desc)
        body = item.newChild(None, "body", None)
        body.newNs(xhtml_ns, None)
        body.newChild(None, "p", escape(pkg.returnSimple('summary')))
        body.newChild(None, "pre", escape(pkg.returnSimple('description')))
        body.newChild(None, "p", 'Change Log:')
        body.newChild(None, "pre", escape(changelog))
        description = '<pre>%s - %s\n\n' % (escape(pkg.name), 
                                            escape(pkg.returnSimple('summary')))
        description += '%s\n\nChange Log:\n\n</pre>' % escape(pkg.returnSimple('description'))
        description += escape('<pre>%s</pre>' % escape(changelog))
        item.newChild(None, 'description', description)
        
        return item
        
    
    def endRSS(self):
        """end the rss output"""
        end="\n  </channel>\n</rss>\n"
        return end
    
        
    def userconfirm(self):
        """gets a yes or no from the user, defaults to No"""
        choice = raw_input('Is this ok [y/N]: ')
        if len(choice) == 0:
            return 0
        else:
            if choice[0] != 'y' and choice[0] != 'Y':
                return 0
            else:
                return 1
                
    
    
    
    def listgroups(self, userlist):
        """lists groups - should handle 'installed', 'all', glob, empty,
           maybe visible and invisible too"""
        # this needs tidying and needs to handle empty statements and globs
        # it also needs to handle a userlist - duh
        # take list - if it's zero then it's '_all_' - push that into list
        # otherwise iterate over list producing output
        if len(userlist) > 0:
            if userlist[0] == "hidden":
                groups = GroupInfo.grouplist
                userlist.pop(0)
            else:
                groups = GroupInfo.visible_groups
        else:
            groups = GroupInfo.visible_groups
        
        if len(userlist) == 0:
            userlist = ['_all_']
    
        groups.sort()
        for item in userlist:
            if item == 'installed':
                print 'Installed Groups'
                for group in groups:
                    if GroupInfo.isGroupInstalled(group):
                        grpid = GroupInfo.group_by_name[group]
                        log(4, '%s - %s' % (grpid, group))
                        print '   %s' % group
            elif item == 'available':
                print 'Available Groups'
                for group in groups:
                    if not GroupInfo.isGroupInstalled(group):
                        grpid = GroupInfo.group_by_name[group]
                        log(4, '%s - %s' % (grpid, group))
                        print '   %s' % group
            elif item == '_all_':
                print 'Installed Groups'
                for group in groups:
                    if GroupInfo.isGroupInstalled(group):
                        grpid = GroupInfo.group_by_name[group]
                        log(4, '%s - %s' % (grpid, group))
                        print '   %s' % group
                        
                print 'Available Groups'
                for group in groups:
                    if not GroupInfo.isGroupInstalled(group):
                        grpid = GroupInfo.group_by_name[group]
                        log(4, '%s - %s' % (grpid, group))
                        print '   %s' % group
            else:
                for group in groups:
                    if group == item or fnmatch.fnmatch(group, item):
                        grpid = GroupInfo.group_by_name[group]
                        log(4, '%s - %s' % (grpid, group))
                        displayPkgsInGroups(group)
    
           
    def format_number(self, number, SI=0, space=' '):
        """Turn numbers into human-readable metric-like numbers"""
        symbols = ['',  # (none)
                    'k', # kilo
                    'M', # mega
                    'G', # giga
                    'T', # tera
                    'P', # peta
                    'E', # exa
                    'Z', # zetta
                    'Y'] # yotta
    
        if SI: step = 1000.0
        else: step = 1024.0
    
        thresh = 999
        depth = 0
    
        # we want numbers between 
        while number > thresh:
            depth  = depth + 1
            number = number / step
    
        # just in case someone needs more than 1000 yottabytes!
        diff = depth - len(symbols) + 1
        if diff > 0:
            depth = depth - diff
            number = number * thresh**depth
    
        if type(number) == type(1) or type(number) == type(1L):
            format = '%i%s%s'
        elif number < 9.95:
            # must use 9.95 for proper sizing.  For example, 9.99 will be
            # rounded to 10.0 with the .1f format string (which is too long)
            format = '%.1f%s%s'
        else:
            format = '%.0f%s%s'
    
        return(format % (number, space, symbols[depth]))

class DepSolveProgressCallBack:
    """provides text output callback functions for Dependency Solver callback"""
    
    def __init__(self):
        # need print functions
        # and error print functions
        # to be set here
        pass
    
    
    def pkgAdded(self, pkginfo, mode):
        pass
        
    def start(self):
        pass
    
    def restartLoop(self):
        pass
    
    def end(self):
        pass
    
    def procReq(self, name, formatted_req):
        pass
    
    def unresolved(self, msg):
        pass
    
    def procConflict(self, name, confname):
        pass
        

    
    
