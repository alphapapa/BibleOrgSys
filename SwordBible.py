#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# SwordBible.py
#
# Module handling Sword Bible files
#
# Copyright (C) 2015 Robert Hunt
# Author: Robert Hunt <Freely.Given.org@gmail.com>
# License: See gpl-3.0.txt
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Module detecting and loading Crosswire Sword Bible binary files.

Files are usually:
    ot
    ot.vss
    nt
    nt.vss
"""

from gettext import gettext as _

LastModifiedDate = '2015-04-17' # by RJH
ShortProgName = "SwordBible"
ProgName = "Sword Bible format handler"
ProgVersion = '0.17'
ProgNameVersion = '{} v{}'.format( ProgName, ProgVersion )
ProgNameVersionDate = '{} {} {}'.format( ProgNameVersion, _("last modified"), LastModifiedDate )

debuggingThisModule = True


import logging, os, re
import multiprocessing

try: import Sword # Assumes that the Sword Python bindings are installed on this computer
except ImportError: # Sword library (dll and python bindings) seem to be not available
    logging.critical( _("You need to install the Sword library with Python3 bindings on your computer in order to use this module.") )

import BibleOrgSysGlobals
from Bible import Bible, BibleBook
from BibleOrganizationalSystems import BibleOrganizationalSystem


 # Must be lowercase
compulsoryTopFolders = ( 'mods.d', 'modules', ) # Both should be there -- the first one contains the .conf file(s)
compulsoryBottomFolders = ( 'rawtext', 'ztext', ) # Either one
compulsoryFiles = ( 'ot','ot.vss', 'ot.bzs','ot.bzv','ot.bzz', 'nt','nt.vss', 'nt.bzs','nt.bzv','nt.bzz', ) # At least two


# Sword enums
DIRECTION_LTR = 0; DIRECTION_RTL = 1; DIRECTION_BIDI = 2
FMT_UNKNOWN = 0; FMT_PLAIN = 1; FMT_THML = 2; FMT_GBF = 3; FMT_HTML = 4; FMT_HTMLHREF = 5; FMT_RTF = 6; FMT_OSIS = 7; FMT_WEBIF = 8; FMT_TEI = 9; FMT_XHTML = 10
ENC_UNKNOWN = 0; ENC_LATIN1 = 1; ENC_UTF8 = 2; ENC_UTF16 = 3; ENC_RTF = 4; ENC_HTML = 5



def SwordBibleFileCheck( givenFolderName, strictCheck=True, autoLoad=False, autoLoadBooks=False ):
    """
    Given a folder, search for Sword Bible files or folders in the folder and in the next level down.

    Returns False if an error is found.

    if autoLoad is false (default)
        returns None, or the number of Bibles found.

    if autoLoad is true and exactly one Sword Bible is found,
        returns the loaded SwordBible object.
    """
    if BibleOrgSysGlobals.verbosityLevel > 2: print( "SwordBibleFileCheck( {}, {}, {} )".format( givenFolderName, strictCheck, autoLoad ) )
    if BibleOrgSysGlobals.debugFlag: assert( givenFolderName and isinstance( givenFolderName, str ) )
    if BibleOrgSysGlobals.debugFlag: assert( autoLoad in (True,False,) )

    # Check that the given folder is readable
    if not os.access( givenFolderName, os.R_OK ):
        logging.critical( _("SwordBibleFileCheck: Given {!r} folder is unreadable").format( givenFolderName ) )
        return False
    if not os.path.isdir( givenFolderName ):
        logging.critical( _("SwordBibleFileCheck: Given {!r} path is not a folder").format( givenFolderName ) )
        return False

    def confirmThisFolder( checkFolderPath ):
        """
        We are given the path to a folder that contains the two main top level folders.

        Now we need to find one or more .conf files and the associated Bible folders.

        Returns a list of Bible module names (without the .conf) -- they are the case of the folder name.
        """
        if BibleOrgSysGlobals.verbosityLevel > 3:
            print( " SwordBibleFileCheck.confirmThisFolder: Looking for files in given {}".format( checkFolderPath ) )

        # See if there's any .conf files in the mods.d folder
        confFolder = os.path.join( checkFolderPath, 'mods.d/' )
        foundConfFiles = []
        for something in os.listdir( confFolder ):
            somepath = os.path.join( confFolder, something )
            if os.path.isdir( somepath ):
                if something == '__MACOSX': continue # don't visit these directories
                print( _("SwordBibleFileCheck: Didn't expect a subfolder in conf folder: {}").format( something ) )
            elif os.path.isfile( somepath ):
                if something.endswith( '.conf' ):
                    foundConfFiles.append( something[:-5].upper() ) # Remove the .conf bit and make it UPPERCASE
                else:
                    logging.warning( _("SwordBibleFileCheck: Didn't expect this file in conf folder: {}").format( something ) )
        if not foundConfFiles: return 0
        #print( foundConfFiles )

        # See if there's folders for the Sword module files matching the .conf files
        compressedFolder = os.path.join( checkFolderPath, 'modules/', 'texts/', 'ztext/' )
        foundTextFolders = []
        for folderType in ( 'rawtext', 'ztext' ):
            mainTextFolder = os.path.join( checkFolderPath, 'modules/', 'texts/', folderType+'/' )
            if os.access( mainTextFolder, os.R_OK ): # The subfolder is readable
                for something in os.listdir( mainTextFolder ):
                    somepath = os.path.join( mainTextFolder, something )
                    if os.path.isdir( somepath ):
                        if something == '__MACOSX': continue # don't visit these directories
                        potentialName = something.upper()
                        if potentialName in foundConfFiles:
                            foundTextFiles = []
                            textFolder = os.path.join( mainTextFolder, something+'/' )
                            for something2 in os.listdir( textFolder ):
                                somepath2 = os.path.join( textFolder, something2 )
                                if os.path.isdir( somepath2 ):
                                    if something2 == '__MACOSX': continue # don't visit these directories
                                    if something2 != 'lucene':
                                        logging.warning( _("SwordBibleFileCheck1: Didn't expect a subfolder in {} text folder: {}").format( something, something2 ) )
                                elif os.path.isfile( somepath2 ):
                                    if folderType == 'rawtext' and something2 in ( 'ot','ot.vss', 'nt','nt.vss' ):
                                        foundTextFiles.append( something2 )
                                    elif folderType == 'ztext' and something2 in ( 'ot.bzs','ot.bzv','ot.bzz', 'nt.bzs','nt.bzv','nt.bzz' ):
                                        foundTextFiles.append( something2 )
                                    else:
                                        if something2 not in ( 'errata', 'appendix', ):
                                            logging.warning( _("SwordBibleFileCheck1: Didn't expect this file in {} text folder: {}").format( something, something2 ) )
                            #print( foundTextFiles )
                            if len(foundTextFiles) >= 2:
                                foundTextFolders.append( something )
                        else:
                            logging.warning( _("SwordBibleFileCheck2: Didn't expect a subfolder in {} folder: {}").format( folderType, something ) )
                    elif os.path.isfile( somepath ):
                        logging.warning( _("SwordBibleFileCheck2: Didn't expect this file in {} folder: {}").format( folderType, something ) )
        if not foundTextFolders:
            if BibleOrgSysGlobals.verbosityLevel > 2: print( "    Looked hopeful but no actual module folders or files found" )
            return None
        #print( foundTextFolders )
        return foundTextFolders
    # end of confirmThisFolder

    # Main part of SwordBibleFileCheck
    # Find all the files and folders in this folder
    if BibleOrgSysGlobals.verbosityLevel > 3:
        print( " SwordBibleFileCheck: Looking for files in given {}".format( givenFolderName ) )
    foundFolders, foundFiles = [], []
    numFound = foundFolderCount = foundFileCount = 0
    for something in os.listdir( givenFolderName ):
        somepath = os.path.join( givenFolderName, something )
        if os.path.isdir( somepath ):
            if something == '__MACOSX': continue # don't visit these directories
            foundFolders.append( something ) # Save folder name in case we have to go a level down
            if something in compulsoryTopFolders:
                foundFolderCount += 1
        elif os.path.isfile( somepath ):
            somethingUpper = something.upper()
            if somethingUpper in compulsoryFiles: foundFileCount += 1
    if foundFolderCount == len(compulsoryTopFolders):
        assert( foundFileCount == 0 )
        foundConfNames = confirmThisFolder( givenFolderName )
        numFound = len(foundConfNames)
    if numFound:
        if BibleOrgSysGlobals.verbosityLevel > 2: print( "SwordBibleFileCheck got", numFound, givenFolderName, foundConfNames )
        if numFound == 1 and (autoLoad or autoLoadBooks):
            oB = SwordBible( givenFolderName )
            if autoLoadBooks: oB.load() # Load and process the file
            return oB
        return numFound
    elif foundFileCount and BibleOrgSysGlobals.verbosityLevel > 2: print( "    Looked hopeful but no actual files found" )

    # Look one level down
    numFound = 0
    foundProjects = []
    numFound = foundFolderCount = foundFileCount = 0
    for thisFolderName in sorted( foundFolders ):
        tryFolderName = os.path.join( givenFolderName, thisFolderName+'/' )
        if not os.access( tryFolderName, os.R_OK ): # The subfolder is not readable
            logging.warning( _("SwordBibleFileCheck: {!r} subfolder is unreadable").format( tryFolderName ) )
            continue
        if BibleOrgSysGlobals.verbosityLevel > 3: print( "    SwordBibleFileCheck: Looking for files in {}".format( tryFolderName ) )
        foundSubfolders, foundSubfiles = [], []
        for something in os.listdir( tryFolderName ):
            somepath = os.path.join( givenFolderName, thisFolderName, something )
            if os.path.isdir( somepath ):
                foundSubfolders.append( something )
                if something in compulsoryTopFolders: foundFolderCount += 1
            elif os.path.isfile( somepath ):
                if somethingUpper in compulsoryFiles: foundFileCount += 1
        if foundFolderCount == len(compulsoryTopFolders):
            assert( foundFileCount == 0 )
            foundConfNames = confirmThisFolder( tryFolderName )
            for confName in foundConfNames:
                foundProjects.append( (tryFolderName,confName) )
                numFound += 1
    if numFound:
        if BibleOrgSysGlobals.verbosityLevel > 2: print( "SwordBibleFileCheck foundProjects", numFound, foundProjects )
        if numFound == 1 and (autoLoad or autoLoadBooks):
            if BibleOrgSysGlobals.debugFlag: assert( len(foundProjects) == 1 )
            oB = SwordBible( foundProjects[0][0], foundProjects[0][1] )
            if autoLoadBooks: oB.load() # Load and process the file
            return oB
        return numFound
# end of SwordBibleFileCheck



def importOSISVerseLine( osisVerseString, thisBook, BBB, C, V ):
    """
    Given a verse entry string made up of OSIS segments,
        convert it into our internal format
        and add the line(s) to thisBook.

    BBB, C, V are just used for more helpful error/information messages.

    OSIS is a pig to extract the information out of,
        but we use it nevertheless because it's the native format
        and hence most likely to represent the original well.

    We use \\NL** as an internal code for a newline
        to show where a verse line needs to be broken into internal chunks.

    Adds the line(s) to thisBook. No return value.
    """
    if BibleOrgSysGlobals.debugFlag and debuggingThisModule:
        print( "importOSISVerseLine( {} {}:{} ... {!r} )".format( BBB, C, V, osisVerseString ) )
    #osisVerseString = osisVerseString.strip()
    verseLine = osisVerseString
    writtenV = False


    def handleWordAttributes( attributeString ):
        """
        Handle OSIS XML attributes from the <w ...> field.

        Returns the string to replace the attributes.
        """
        attributeReplacementResult = ''
        attributeCount = attributeString.count( '="' )
        #print( 'Attributes={} {!r}'.format( attributeCount, attributeString ) )
        for j in range( 0, attributeCount ):
            match2 = re.search( 'savlm="(.+?)"', attributeString )
            if match2:
                savlm = match2.group(1)
                #print( 'savlm', repr(savlm) )
                while True:
                    match3 = re.search( 'strong:([GH]\d{1,5})', savlm )
                    if not match3: break
                    #print( 'string', repr(match3.group(1) ) )
                    attributeReplacementResult += '\\str {}\\str*'.format( match3.group(1) )
                    savlm = savlm[:match3.start()] + savlm[match3.end():] # Remove this Strongs' number
                attributeString = attributeString[:match2.start()] + attributeString[match2.end():] # Remove this attribute entry

            match2 = re.search( 'type="(.+?)"', attributeString )
            if match2:
                typeValue = match2.group(1)
                #print( 'typeValue', repr(typeValue) ) # Seems to have an incrementing value on the end for some reason
                assert( typeValue.startswith( 'x-split' ) ) # e.g., x-split or x-split-1 -- what do these mean?
                attributeString = attributeString[:match2.start()] + attributeString[match2.end():] # Remove this attribute entry
            match2 = re.search( 'subType="(.+?)"', attributeString )
            if match2:
                subType = match2.group(1)
                #print( 'subType', repr(subType) ) # e.g., x-28 -- what does this mean?
                attributeString = attributeString[:match2.start()] + attributeString[match2.end():] # Remove this attribute entry

            match2 = re.search( 'src="(.+?)"', attributeString ) # Can be two numbers separated by a space!
            if match2:
                src = match2.group(1)
                #print( 'src', repr(src) ) # What does this mean?
                attributeString = attributeString[:match2.start()] + attributeString[match2.end():] # Remove this attribute entry

            match2 = re.search( 'wn="(\d+?)"', attributeString )
            if match2:
                wn = match2.group(1)
                #print( 'wn', repr(wn) ) # What does this mean?
                attributeString = attributeString[:match2.start()] + attributeString[match2.end():] # Remove this attribute entry

        if attributeString.strip():
            print( 'Unhandled word attributes', repr(attributeString) )
            if BibleOrgSysGlobals.debugFlag: halt
        #print( 'attributeReplacementResult', repr(attributeReplacementResult) )
        return attributeReplacementResult
    # end of handleWordAttributes


    # Start of main code for importOSISVerseLine
    # Straight substitutions
    for old, new in ( ( '<milestone marker="¶" type="x-p"/>', '\\NL**\\p\\NL**' ),
                      ( '<milestone marker="¶" subType="x-added" type="x-p"/>', '\\NL**\\p\\NL**' ),
                      ( '<milestone type="x-extra-p"/>', '\\NL**\\p\\NL**' ),
                      ( '<lb/>', '\\NL**' ),
                      ( '<list>', '\\NL**' ), ( '</list>', '\\NL**' ),
                      ):
        verseLine = verseLine.replace( old, new )

    # Now scan for fixed open and close fields
    for openCode,newOpenCode,closeCode,newCloseCode in ( ('<transChange type="added">','\\add ','</transChange>','\\add*'),
                                                        ('<seg><divineName>','\\nd ','</divineName></seg>','\\nd*'),
                                                        ('<divineName>','\\nd ','</divineName>','\\nd*'),
                                                        ('<speaker>','\\sp ','</speaker>','\\sp*'),
                                                        ('<inscription>','\\bdit ','</inscription>','\\bdit*'), # What should this really be?
                                                        #('<foreign>','\\tl ','</foreign>','\\tl*'),
                                                        #('\x1f','STARTF','\x1f','ENDF'),
                                                        #('[','\\add',']','\\add*'),
                                                        #('\\\\  #','\\xt','\\\\',''),
                                                        ):
        ix = verseLine.find( openCode )
        while ix != -1:
            #print( '{} {!r}->{!r} {!r}->{!r} in {!r}'.format( ix, openCode,newOpenCode,closeCode,newCloseCode, verseLine ) )
            verseLine = verseLine.replace( openCode, newOpenCode, 1 )
            ixEnd = verseLine.find( closeCode, ix )
            if ixEnd == -1:
                logging.error( 'Missing {!r} close code to match {!r}'.format( closeCode, openCode ) )
                verseLine = verseLine + newCloseCode # Try to fix it by adding a closing code at the end
            else:
                verseLine = verseLine.replace( closeCode, newCloseCode, 1 )
            ix = verseLine.find( openCode, ix )
        if verseLine.find( closeCode ) != -1:
            logging.error( 'Unexpected {!r} close code without any previous {!r}'.format( closeCode, openCode )  )
            verseLine = newOpenCode + verseLine.replace( closeCode, newCloseCode, 1 ) # Try to fix it by adding an opening code at the beginning

    # Delete end book and chapter (self-closing) markers (we'll add our own later)
    while True: # Delete end book markers (should only be maximum of one theoretically but not always so)
        match = re.search( '<div [^/>]*?eID=[^/>]+?/>', verseLine )
        if not match: break
        verseLine = verseLine[:match.start()] + verseLine[match.end():]
    while True: # Delete preverse milestones
        match = re.search( '<div [^/>]*?subType="x-preverse"[^/>]*?/>', verseLine )
        if not match: break
        verseLine = verseLine[:match.start()] + verseLine[match.end():]
    while True:
        match = re.search( '<div [^/>]*?type="front"[^/>]*?/>', verseLine )
        if not match: break
        assert( V == '0' )
        verseLine = verseLine[:match.start()] + verseLine[match.end():] # It's in v0 anyway so no problem
    while True:
        match = re.search( '<div [^/>]*?type="colophon"[^/>]*?/>', verseLine )
        if not match: break
        verseLine = verseLine[:match.start()] + verseLine[match.end():] # Not sure what this is (Rom 16:27) but delete it for now
    while True: # Delete end chapter markers (should only be maximum of one theoretically)
        match = re.search( '<chapter [^/>]*?eID=[^/>]+?/>', verseLine )
        if not match: break
        verseLine = verseLine[:match.start()] + verseLine[match.end():]
    while True: # Delete lg start and end milestones
        match = re.search( '<lg [^/>]+?/>', verseLine )
        if not match: break
        verseLine = verseLine[:match.start()] + verseLine[match.end():]
    # Regular expression replacements

    # Other regular expression data extractions
    match = re.search( '<chapter ([^/>]*?)sID="([^/>]+?)"([^/>]*?)/>', verseLine )
    if match:
        attributes, sID = match.group(1) + match.group(3), match.group(2)
        #print( 'Chapter sID {!r} attributes={!r} @ {} {}:{}'.format( sID, attributes, BBB, C, V ) )
        assert( C and C != '0' )
        assert( V == '0' )
        #assert( osisVerseString.startswith( '<chapter ' ) # It's right at the beginning
               #or osisVerseString.startswith( '<title> <chapter ' ) ) # or nearby
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule: print( "CCCC {!r}(:{!r})".format( C, V ) )
        thisBook.addLine( 'c', C )
        #replacement = '\\NL**\\c {}\\NL**'.format( C )
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + verseLine[match.end():]
    while True:
        match = re.search( '<div ([^/>]*?)type="([^/>]+?)"([^/>]*?)/><title>(.+?)</title>', verseLine )
        if not match: break
        attributes, sectionType, words = match.group(1) + match.group(3), match.group(2), match.group(4)
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule:
            print( 'Section title {!r} attributes={!r} Words={!r}'.format( sectionType, attributes, words ) )
        if sectionType == 'section': titleMarker = 's1'
        elif sectionType == 'subSection': titleMarker = 's2'
        elif sectionType == 'x-subSubSection': titleMarker = 's3'
        elif sectionType == 'majorSection': titleMarker = 'sr'
        else: halt
        replacement = '\\NL**\\{} {}\\NL**'.format( titleMarker, words )
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
    match = re.search( '<div ([^/>]*?)type="([^/>]+?)"([^/>]*?)/><title>', verseLine )
    if match: # handle left over div/title start fields
        attributes, sectionType = match.group(1) + match.group(3), match.group(2)
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule:
            print( 'Section title start {!r} attributes={!r}'.format( sectionType, attributes ) )
        if sectionType == 'section': titleMarker = 's1'
        elif sectionType == 'subSection': titleMarker = 's2'
        elif sectionType == 'x-subSubSection': titleMarker = 's3'
        else: halt
        replacement = '\\NL**\\{} '.format( titleMarker )
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
    while True:
        match = re.search( '<div ([^/>]*?)type="([^/>]+?)"([^/>]*?)/>.NL..<head>(.+?)</head>', verseLine )
        if not match: break
        attributes, sectionType, words = match.group(1) + match.group(3), match.group(2), match.group(4)
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule: print( 'Section title {!r} attributes={!r} Words={!r}'.format( sectionType, attributes, words ) )
        if sectionType == 'outline': titleMarker = 'iot'
        else: halt
        replacement = '\\NL**\\{} {}\\NL**'.format( titleMarker, words )
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
    while True:
        match = re.search( '<div ([^/>]*?)type="([^/>]+?)"([^/>]*?)/>', verseLine )
        if not match: break
        attributes, divType = match.group(1) + match.group(3), match.group(2)
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule: print( 'Div type={!r} attributes={!r}'.format( divType, attributes ) )
        if divType == 'x-p': replacement = '\\NL**\\p\\NL**'
        elif divType == 'glossary': replacement = '\\NL**\\id GLO\\NL**' #### WEIRD -- appended to 3 John
        elif divType == 'book': replacement = '' # We don't need this
        elif divType == 'outline': replacement = '\\NL**\\iot\\NL**'
        elif divType == 'paragraph': replacement = '\\NL**\\p\\NL**'
        elif divType == 'majorSection': replacement = '\\NL**\\ms\\NL**'
        else: halt
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
    while True:
        match = re.search( '<title type="parallel"><reference type="parallel">(.+?)</reference></title>', verseLine )
        if not match: break
        reference = match.group(1)
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule: print( 'Parallel reference={!r}'.format( reference ) )
        replacement = '\\NL**\\r {}\\NL**'.format( reference )
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
    while True:
        match = re.search( '<title type="scope"><reference>(.+?)</reference></title>', verseLine )
        if not match: break
        reference = match.group(1)
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule: print( 'Section Parallel reference={!r}'.format( reference ) )
        replacement = '\\NL**\\sr {}\\NL**'.format( reference )
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
    while True:
        match = re.search( '<title ([^/>]+?)>(.+?)</title>', verseLine )
        if not match: break
        attributes, words = match.group(1), match.group(2)
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule: print( 'Title attributes={!r} Words={!r}'.format( attributes, words ) )
        titleMarker = 's1'
        replacement = '\\NL**\\{} {}\\NL**'.format( titleMarker, words )
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
    verseLine = verseLine.replace( '</title>', '\\NL**' )
    verseLine = verseLine.replace( '<title>', '\\NL**\\s ' )
    while True:
        match = re.search( '<w ([^/>]+?)/>', verseLine )
        if not match: break
        replacement = handleWordAttributes( match.group(1) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
        #print( "verseLineB", repr(verseLine) )
    while True:
        match = re.search( '<w ([^/>]+?)>(.+?)</w>', verseLine )
        if not match: break
        attributes, words = match.group(1), match.group(2)
        #print( 'AttributesC={!r} Words={!r}'.format( attributes, words ) )
        replacement = words
        replacement += handleWordAttributes( attributes )
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
        #print( "verseLineC", repr(verseLine) )
    while True:
        match = re.search( '<q ([^/>]+?)>(.+?)</q>', verseLine )
        if not match: break
        attributes, words = match.group(1), match.group(2)
        if 'who="Jesus"' in attributes:
            if 'marker="' in attributes and 'marker=""' not in attributes:
                print( 'AttributesQM={!r} Words={!r}'.format( attributes, words ) )
                halt
            replacement = '\\wj {}\\wj*'.format( words )
        else:
            print( 'AttributesQ={!r} Words={!r}'.format( attributes, words ) )
            if BibleOrgSysGlobals.debugFlag: halt
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
    while True:
        match = re.search( '<l ([^/>]*?)level="(.+?)"([^/>]*?)/>', verseLine )
        if not match: break
        attributes, level = match.group(1)+match.group(3), match.group(2)
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule: print( 'AttributesL={!r} Level={!r}'.format( attributes, level ) )
        assert( level in '1234' )
        if 'sID="' in attributes:
            replacement = '\\NL**\\q{} '.format( level )
        elif 'eID="' in attributes:
            replacement = '' # Remove eIDs completely
        else:
            print( 'AttributesLeID={!r} Level={!r}'.format( attributes, level ) )
            halt
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
    while True: # handle list items
        match = re.search( '<item ([^/>]*?)type="(.+?)"([^/>]*?)>(.+?)</item>', verseLine )
        if not match: break
        attributes, itemType, item = match.group(1)+match.group(3), match.group(2), match.group(4)
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule: print( 'Item={!r} Type={!r} attributes={!r}'.format( item, itemType, attributes ) )
        assert( itemType in ( 'x-indent-1', 'x-indent-2', ) )
        marker = 'io' if 'x-introduction' in attributes else 'li'
        replacement = '\\NL**\\{} {}\\NL**'.format( marker+itemType[-1], item )
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
    match = re.search( '<item ([^/>]*?)type="(.+?)"([^/>]*?)>', verseLine )
    if match: # Handle left-over list items
        attributes, itemType = match.group(1)+match.group(3), match.group(2)
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule: print( 'Item Type={!r} attributes={!r}'.format( itemType, attributes ) )
        assert( itemType in ( 'x-indent-1', 'x-indent-2', ) )
        marker = 'io' if 'x-introduction' in attributes else 'li'
        replacement = '\\NL**\\{}\\NL**'.format( marker+itemType[-1] )
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
    verseLine = verseLine.replace( '</item>', '\\NL**' )
    while True: # handle names
        match = re.search( '<name ([^/>]*?)type="(.+?)"([^/>]*?)>(.+?)</name>', verseLine )
        if not match: break
        attributes, nameType, name = match.group(1)+match.group(3), match.group(2), match.group(4)
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule: print( 'Name={!r} Type={!r} attributes={!r}'.format( name, nameType, attributes ) )
        if nameType == 'x-workTitle': marker = 'bk'
        else: halt
        replacement = '\\{} {}\\{}*'.format( marker, name, marker )
        print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
    while True:
        match = re.search( '<seg ([^/>]+?)>([^<]+?)</seg>', verseLine )
        if not match: break
        attributes, words = match.group(1), match.group(2)
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule: print( 'Seg attributes={!r} Words={!r}'.format( attributes, words ) )
        if 'type="keyword"' in attributes: marker = 'k'
        elif 'type="x-transChange"' in attributes and 'subType="x-added"' in attributes: marker = 'add'
        else: halt
        replacement = '\\{} {}\\{}*'.format( marker, words, marker )
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
        #print( "verseLineC", repr(verseLine) )
    while True:
        match = re.search( '<foreign ([^/>]+?)>(.+?)</foreign>', verseLine )
        if not match: break
        attributes, words = match.group(1), match.group(2)
        #print( 'Attributes={!r} Words={!r}'.format( attributes, words ) )
        replacement = '\\tl {}\\tl*'.format( words )
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
        #print( "verseLineC", repr(verseLine) )
    while True:
        match = re.search( '<reference([^/>]*?)>(.+?)</reference>', verseLine )
        if not match: break
        attributes, referenceField = match.group(1), match.group(2)
        #print( 'Attributes={!r} referenceField={!r}'.format( attributes, referenceField ) )
        marker = 'ior' if V=='0' else 'XXX'
        replacement = '\\{} {}\\{}*'.format( marker, referenceField, marker )
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
        #print( "verseLineC", repr(verseLine) )
    while True:
        match = re.search( '<hi ([^/>]+?)>(.+?)</hi>', verseLine )
        if not match: break
        attributes, words = match.group(1), match.group(2)
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule: print( 'Highlight attributes={!r} Words={!r}'.format( attributes, words ) )
        if '"italic"' in attributes: marker = 'it'
        else: halt
        replacement = '\\{} {}\\{}*'.format( marker, words, marker )
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
        #print( "verseLineC", repr(verseLine) )
    while True:
        match = re.search( '<milestone ([^/>]*?)type="x-usfm-(.+?)"([^/>]*?)/>', verseLine )
        if not match: break
        attributes, marker = match.group(1)+match.group(3), match.group(2)
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule: print( 'Milestone attributes={!r} marker={!r}'.format( attributes, marker ) )
        match2 = re.search( 'n="(.+?)"', attributes )
        if match2:
            replacement = '\\NL**\\{} {}\\NL**'.format( marker, match2.group(1) )
            #print( 'replacement', repr(replacement) )
        else: replacement = ''; halt
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]
        #print( "verseLineC", repr(verseLine) )
    while True: # Not sure what this is all about -- just delete it
        match = re.search( '<milestone ([^/>]*?)type="x-strongsMarkup"([^/>]*?)/>', verseLine )
        if not match: break
        attributes = match.group(1)+match.group(2)
        print( 'Strongs milestone attributes={!r}'.format( attributes ) )
        verseLine = verseLine[:match.start()] + verseLine[match.end():]
        #print( "verseLineC", repr(verseLine) )
    while True:
        match = re.search( '<note ([^/>]*?)swordFootnote="([^/>]+?)"([^/>]*?)>(.*?)</note>', verseLine )
        if not match: break
        attributes, number, noteContents = match.group(1)+match.group(3), match.group(2), match.group(4)
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule: print( 'Note={!r} Number={!r}'.format( attributes, number ) )
        if 'crossReference' in attributes:
            assert( noteContents == '' )
            replacement = '\\x {}\\x*'.format( number )
        else: halt
        #print( 'replacement', repr(replacement) )
        verseLine = verseLine[:match.start()] + replacement + verseLine[match.end():]

    if '<' in verseLine or '>' in verseLine or '=' in verseLine or '"' in verseLine:
        print( "verseLine", repr(verseLine) )
        if BibleOrgSysGlobals.debugFlag:
            if BBB!='PSA' or V not in ('1','5',): halt
    #if V == '3': halt

    #print( "FFFFFFFFFFF", repr(verseLine) )
    while '  ' in verseLine: verseLine = verseLine.replace( '  ', ' ' ) # Reduce double spaces
    while '\\NL** ' in verseLine: verseLine = verseLine.replace( '\\NL** ', '\\NL**' ) # Remove spaces before newlines
    while ' \\NL**' in verseLine: verseLine = verseLine.replace( ' \\NL**', '\\NL**' ) # Remove spaces after newlines
    while '\\NL**\\NL**' in verseLine: verseLine = verseLine.replace( '\\NL**\\NL**', '\\NL**' ) # Don't need double-ups
    if verseLine.startswith( '\\NL**' ): verseLine = verseLine[5:] # Don't need nl at start of verseLine
    if verseLine.endswith( '\\p \\NL**'): verseLine = verseLine[:-6] # Don't need nl and then space at end of verseLine
    if verseLine.endswith( '\\q1 \\NL**'): verseLine = verseLine[:-6] # Don't need nl and then space at end of verseLine
    if verseLine.endswith( '\\q2 \\NL**'): verseLine = verseLine[:-6] # Don't need nl and then space at end of verseLine
    if verseLine.endswith( '\\q3 \\NL**'): verseLine = verseLine[:-6] # Don't need nl and then space at end of verseLine
    if verseLine.endswith( '\\q4 \\NL**'): verseLine = verseLine[:-6] # Don't need nl and then space at end of verseLine
    if verseLine.endswith( '\\NL**' ): verseLine = verseLine[:-5] # Don't need nl at end of verseLine
    verseLine = verseLine.replace( '\\s1 \\p', '\\p' ) # Delete useless s1 heading marker
    verseLine = verseLine.replace( '\\wj\\NL**\\p\\NL**', '\\NL**\\p\\NL**\\wj ' ) # Start wj after paragraph marker
    verseLine = verseLine.strip()
    if '\\NL**' in verseLine: # We need to break the original line into different USFM markers
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule:
            print( "\nMessing with segments: {} {}:{} {!r}".format( BBB, C, V, verseLine ) )
        segments = verseLine.split( '\\NL**' )
        if BibleOrgSysGlobals.debugFlag and debuggingThisModule:
            assert( len(segments) >= 2 )
            print( "\n segments (split by \\NL**):", segments )
        leftovers = ''
        for segment in segments:
            if segment and segment[0] == '\\':
                bits = segment.split( None, 1 )
                #print( " bits", bits )
                marker = bits[0][1:]
                if len(bits) == 1:
                    #if bits[0] in ('\\p','\\b'):
                    if BibleOrgSysGlobals.USFMMarkers.isNewlineMarker( marker ):
                        #if C==1 and V==1 and not appendedCFlag: thisBook.addLine( 'c', str(C) ); appendedCFlag = True
                        thisBook.addLine( marker, '' )
                    else:
                        logging.error( "It seems that we had a blank {!r} field \nin {!r} \nfrom {!r}".format( bits[0], verseLine, osisVerseString ) )
                        if BibleOrgSysGlobals.debugFlag: halt
                else:
                    assert( len(bits) == 2 )
                    if BibleOrgSysGlobals.debugFlag and debuggingThisModule:
                        print( "\n{} {}:{} {!r}".format( BBB, C, V, osisVerseString ) )
                        print( "verseLine", repr(verseLine) )
                        print( "seg", repr(segment) )
                        print( "segments:", segments )
                        print( "bits", bits )
                        print( "marker", marker )
                        print( "leftovers", repr(leftovers) )
                        assert( marker in ( 'id', 'toc1','toc2','toc3', 'mt1','mt2','mt3', 'iot','io1','io2','io3',
                                           's1','s2','s3', 'r','sr','sp', 'q1','q2','q3', 'v', 'li1','li2','li2', )
                               or marker in ( 'x', 'bk', 'wj', 'nd', 'add', 'k', 'bd','bdit','it', 'str', ) ) # These ones are character markers which can start a new line
                    if BibleOrgSysGlobals.USFMMarkers.isNewlineMarker( marker ):
                        thisBook.addLine( marker, bits[1] )
                    elif not writtenV:
                        thisBook.addLine( 'v', '{} {}'.format( V, segment ) )
                        writtenV = True
                    else: leftovers += segment
            else: # What is segment is blank (\\NL** at end of verseLine)???
                #if C==1 and V==1 and not appendedCFlag: thisBook.addLine( 'c', str(C) ); appendedCFlag = True
                if not writtenV:
                    thisBook.addLine( 'v', '{} {}'.format( V, leftovers+segment ) )
                    writtenV = True
                else:
                    thisBook.addLine( 'v~', leftovers+segment )
                leftovers = ''
                #if myGlobals['haveParagraph']:
                    #thisBook.addLine( 'p', '' )
                    #myGlobals['haveParagraph'] = False
        if leftovers:
            if BibleOrgSysGlobals.debugFlag and debuggingThisModule:
                print( "\noVS", repr(osisVerseString) )
                print( "\nvL", repr(verseLine) )
            #logging.critical( "Had leftovers {}".format( repr(leftovers) ) )
            thisBook.appendToLastLine( leftovers )
    elif verseLine: # No newlines in result
        thisBook.addLine( 'v', V + ' ' + verseLine )
# end of importOSISVerseLine



def importGBFVerseLine( gbfVerseString, thisBook, BBB, C, V ):
    """
    Given a verse entry string made up of GBF segments,
        convert it into our internal format
        and add the line(s) to thisBook.

    BBB, C, V are just used for more helpful error/information messages.

    We use \\NL** as an internal code for a newline
        to show where a verse line needs to be broken into internal chunks.

    Adds the line(s) to thisBook. No return value.
    """
    if BibleOrgSysGlobals.debugFlag and debuggingThisModule:
        print( "importGBFVerseLine( {} {}:{} ... {!r} )".format( BBB, C, V, gbfVerseString ) )
    #osisVerseString = osisVerseString.strip()
    verseLine = gbfVerseString
    writtenV = False

    # Start of main code for importGBFVerseLine
    # Straight substitutions
    for old, new in ( ( '<CM>', '\\NL**\\p\\NL**' ),
                      #( '<milestone marker="¶" subType="x-added" type="x-p"/>', '\\NL**\\p\\NL**' ),
                      #( '<milestone type="x-extra-p"/>', '\\NL**\\p\\NL**' ),
                      #( '<lb/>', '\\NL**' ),
                      #( '<list>', '\\NL**' ), ( '</list>', '\\NL**' ),
                      ):
        verseLine = verseLine.replace( old, new )

    # Now scan for fixed open and close fields
    for openCode,newOpenCode,closeCode,newCloseCode in ( ('<FI>','\\it ','<Fi>','\\it*'),
                                                        #('<seg><divineName>','\\nd ','</divineName></seg>','\\nd*'),
                                                        #('<divineName>','\\nd ','</divineName>','\\nd*'),
                                                        #('<speaker>','\\sp ','</speaker>','\\sp*'),
                                                        #('<inscription>','\\bdit ','</inscription>','\\bdit*'), # What should this really be?
                                                        #('<foreign>','\\tl ','</foreign>','\\tl*'),
                                                        #('\x1f','STARTF','\x1f','ENDF'),
                                                        #('[','\\add',']','\\add*'),
                                                        #('\\\\  #','\\xt','\\\\',''),
                                                        ):
        ix = verseLine.find( openCode )
        while ix != -1:
            #print( '{} {!r}->{!r} {!r}->{!r} in {!r}'.format( ix, openCode,newOpenCode,closeCode,newCloseCode, verseLine ) )
            verseLine = verseLine.replace( openCode, newOpenCode, 1 )
            ixEnd = verseLine.find( closeCode, ix )
            if ixEnd == -1:
                logging.error( 'Missing {!r} close code to match {!r}'.format( closeCode, openCode ) )
                verseLine = verseLine + newCloseCode # Try to fix it by adding a closing code at the end
            else:
                verseLine = verseLine.replace( closeCode, newCloseCode, 1 )
            ix = verseLine.find( openCode, ix )
        if verseLine.find( closeCode ) != -1:
            logging.error( 'Unexpected {!r} close code without any previous {!r}'.format( closeCode, openCode )  )
            verseLine = newOpenCode + verseLine.replace( closeCode, newCloseCode, 1 ) # Try to fix it by adding an opening code at the beginning


    if '<' in verseLine or '>' in verseLine or '=' in verseLine or '"' in verseLine:
        print( "verseLine", repr(verseLine) )
        if BibleOrgSysGlobals.debugFlag: halt

    print( "Got vL: {}".format( verseLine ) )
    thisBook.addLine( 'v', V + ' ' + verseLine )
# end of importGBFVerseLine



class SwordBible( Bible ):
    """
    Class for reading, validating, and converting SwordBible files.
    """
    def __init__( self, sourceFolder, moduleName=None, encoding='utf-8' ):
        """
        Constructor: just sets up the Bible object.

        The sourceFolder should be the one containing mods.d and modules folders.
        The module name (if needed) should be the name of one of the .conf files in the mods.d folder
            (with or without the .conf on it).
        """
        #print( "SwordBible.__init__( {} {} {} )".format( sourceFolder, moduleName, encoding ) )

         # Setup and initialise the base class first
        Bible.__init__( self )
        self.objectNameString = "Sword Bible object"
        self.objectTypeString = "Sword"

        # Now we can set our object variables
        self.sourceFolder, self.moduleName, self.encoding = sourceFolder, moduleName, encoding
        #self.sourceFilepath =  os.path.join( self.sourceFolder, self.givenName+'_utf8.txt' )

        # Do a preliminary check on the readability of our file
        if not os.access( self.sourceFolder, os.R_OK ):
            logging.critical( _("SwordBible: Folder {!r} is unreadable").format( self.sourceFolder ) )

        if not self.moduleName: # If we weren't passed the module name, we need to assume that there's only one
            confFolder = os.path.join( self.sourceFolder, 'mods.d/' )
            foundConfs = []
            for something in os.listdir( confFolder ):
                somepath = os.path.join( confFolder, something )
                if os.path.isfile( somepath ) and something.endswith( '.conf' ):
                    foundConfs.append( something[:-5] ) # Drop the .conf bit
            if foundConfs == 0:
                logging.critical( "No .conf files found in {}".format( confFolder ) )
            elif len(foundConfs) > 1:
                logging.critical( "Too many .conf files found in {}".format( confFolder ) )
            else:
                print( "Got", foundConfs[0] )
                self.moduleName = foundConfs[0]

        # Load the Sword manager and find our module
        self.SWMgr = Sword.SWMgr()
        self.SWMgr.augmentModules( sourceFolder, False ) # Add our folder to the SW Mgr
        availableModuleCodes = []
        for j,moduleBuffer in enumerate(self.SWMgr.getModules()):
            moduleID = moduleBuffer.getRawData()
            if moduleID.upper() == self.moduleName.upper(): self.moduleName = moduleID # Get the case correct
            #module = SWMgr.getModule( moduleID )
            #if 0:
                #print( "{} {} ({}) {} {!r}".format( j, module.getName(), module.getType(), module.getLanguage(), module.getEncoding() ) )
                #try: print( "    {} {!r} {} {}".format( module.getDescription(), module.getMarkup(), module.getDirection(), "" ) )
                #except UnicodeDecodeError: print( "   Description is not Unicode!" )
            #print( "moduleID", repr(moduleID) )
            availableModuleCodes.append( moduleID )
        if self.moduleName not in availableModuleCodes:
            logging.critical( "Unable to find {!r} Sword module".format( self.moduleName ) )
            if BibleOrgSysGlobals.debugFlag and BibleOrgSysGlobals.verbosityLevel > 2:
                print( "Available module codes:", availableModuleCodes )

        self.abbreviation = self.moduleName
        #print( 'MMMM', self.moduleName ); halt
    # end of SwordBible.__init__


    def load( self ):
        """
        Load the compressed data file and import book elements.
        """
        if BibleOrgSysGlobals.verbosityLevel > 1: print( _("\nLoading {} module...").format( self.moduleName ) )
        module = self.SWMgr.getModule( self.moduleName )
        if module is None:
            logging.critical( "Unable to load {!r} module -- not known by Sword".format( self.moduleName ) )
            return

        if BibleOrgSysGlobals.verbosityLevel > 3:
            print( 'Description: {!r}'.format( module.getDescription() ) )
            print( 'Direction: {!r}'.format( ord(module.getDirection()) ) )
            print( 'Encoding: {!r}'.format( ord(module.getEncoding()) ) )
            print( 'KeyText: {!r}'.format( module.getKeyText() ) )
            print( 'Language: {!r}'.format( module.getLanguage() ) )
            print( 'Markup: {!r}'.format( ord(module.getMarkup()) ) )
            print( 'Name: {!r}'.format( module.getName() ) )
            print( 'RawEntry: {!r}'.format( module.getRawEntry() ) )
            print( 'RenderHeader: {!r}'.format( module.getRenderHeader() ) )
            print( 'Type: {!r}'.format( module.getType() ) )
            print( 'IsSkipConsecutiveLinks: {!r}'.format( module.isSkipConsecutiveLinks() ) )
            print( 'IsUnicode: {!r}'.format( module.isUnicode() ) )
            print( 'IsWritable: {!r}'.format( module.isWritable() ) )
            #print( 'Name: {!r}'.format( module.getName() ) )
            #return

        #BBB, C, V = 'GEN', '1', '1'
        #B = BibleOrgSysGlobals.BibleBooksCodes.getOSISAbbreviation( BBB )
        #refString = "{} {}:{}".format( B, C, V )
        #print( 'refString', refString )
        #verseKey = Sword.VerseKey( refString )
        #print( verseKey.getShortText() )
        #module.setKey( verseKey )
        #for j in range ( 0, 31102 ):
            #print( module.getName(), module.getKey().getShortText(), module.renderText() )
            #print( module.getName(), module.getKey().getShortText(), module.stripText() )
            #module.increment()

        # Main code for load()
        markupCode = ord( module.getMarkup() )
        encoding = ord( module.getEncoding() )
        if encoding == ENC_LATIN1: self.encoding = 'latin-1'
        elif encoding == ENC_UTF8: self.encoding = 'utf-8'
        elif encoding == ENC_UTF16: self.encoding = 'utf-16'
        elif BibleOrgSysGlobals.debugFlag: halt

        bookCount = 0
        currentBBB = None
        for index in range( 0, 999999 ):
            module.setIndex( index )
            if module.getIndex() != index: break # Gone too far

            # Find where we're at
            verseKey = module.getKey()
            verseKeyText = verseKey.getShortText()
            #if BibleOrgSysGlobals.debugFlag and debuggingThisModule:
                #print( 'vkst={!r} vkix={}'.format( verseKeyText, verseKey.getIndex() ) )

            #nativeVerseText = module.renderText().decode( self.encoding, 'replace' )
            #nativeVerseText = str( module.renderText() ) if self.encoding=='utf-8' else str( module.renderText(), encoding=self.encoding )
            try: nativeVerseText = str( module.renderText() )
            except UnicodeDecodeError: nativeVerseText = ''

            if ':' not in verseKeyText:
                print( "Unusual key: {!r} gave {!r}".format( verseKeyText, nativeVerseText ) )
                if BibleOrgSysGlobals.debugFlag:
                    assert( verseKeyText in ( '[ Module Heading ]', '[ Testament 1 Heading ]', '[ Testament 2 Heading ]', ) )
                if BibleOrgSysGlobals.verbosityLevel > 3:
                    if markupCode == FMT_OSIS:
                        match = re.search( '<milestone ([^/>]*?)type="x-importer"([^/>]*?)/>', nativeVerseText )
                        if match:
                            attributes = match.group(1) + match.group(2)
                            match2 = re.search( 'subType="(.+?)"', attributes )
                            subType = match2.group(1) if match2 else None
                            if subType and subType.startswith( 'x-' ): subType = subType[2:] # Remove the x- prefix
                            match2 = re.search( 'n="(.+?)"', attributes )
                            n = match2.group(1) if match2 else None
                            if n: n = n.replace( '$', '' ).strip()
                            print( "Module created by {} {}".format( subType, n ) )
                continue
            vkBits = verseKeyText.split()
            assert( len(vkBits) == 2 )
            osisBBB = vkBits[0]
            BBB = BibleOrgSysGlobals.BibleBooksCodes.getBBBFromOSIS( osisBBB )
            if isinstance( BBB, list ): BBB = BBB[0] # We sometimes get a list of options -- take the first = most likely one
            vkBits = vkBits[1].split( ':' )
            assert( len(vkBits) == 2 )
            C, V = vkBits
            #print( 'At {} {}:{}'.format( BBB, C, V ) )

            # Start a new book if necessary
            if BBB != currentBBB:
                if currentBBB is not None: # Save the previous book
                    if BibleOrgSysGlobals.verbosityLevel > 3: print( "Saving", currentBBB, bookCount )
                    self.saveBook( thisBook )
                # Create the new book
                if BibleOrgSysGlobals.verbosityLevel > 2:  print( '  Loading {} {}...'.format( self.moduleName, BBB ) )
                thisBook = BibleBook( self, BBB )
                thisBook.objectNameString = "Sword Bible Book object"
                thisBook.objectTypeString = "Sword Bible"
                currentBBB, currentC = BBB, '0'
                bookCount += 1
            #if C != currentC:
                #thisBook.addLine( 'c', C )
                #currentC = C

            if markupCode == FMT_OSIS: importOSISVerseLine( nativeVerseText, thisBook, BBB, C, V )
            elif markupCode == FMT_GBF: importGBFVerseLine( nativeVerseText, thisBook, BBB, C, V )
            else:
                print( 'markupCode', repr(markupCode) )
                if BibleOrgSysGlobals.debugFlag: halt
                return

        if currentBBB is not None: # Save the very last book
            if BibleOrgSysGlobals.verbosityLevel > 3: print( "Saving", self.moduleName, currentBBB, bookCount )
            self.saveBook( thisBook )

        self.doPostLoadProcessing()
    # end of SwordBible.load
# end of SwordBible class



def testSwB( SwFolderPath, SwModuleName ):
    """
    Crudely demonstrate the Sword Bible class
    """
    import VerseReferences

    if BibleOrgSysGlobals.verbosityLevel > 1: print( _("Demonstrating the Sword Bible class...") )
    if BibleOrgSysGlobals.verbosityLevel > 0: print( "  Test folder is {!r} {!r}".format( SwFolderPath, SwModuleName ) )
    SwBible = SwordBible( SwFolderPath, SwModuleName )
    SwBible.load() # Load and process the file
    if BibleOrgSysGlobals.verbosityLevel > 1: print( SwBible ) # Just print a summary
    if BibleOrgSysGlobals.strictCheckingFlag:
        SwBible.check()
        #print( UsfmB.books['GEN']._processedLines[0:40] )
        SwBErrors = SwBible.getErrors()
        # print( SwBErrors )
    if BibleOrgSysGlobals.commandLineOptions.export:
        ##SwBible.toDrupalBible()
        SwBible.doAllExports( wantPhotoBible=False, wantODFs=False, wantPDFs=False )
    for reference in ( ('OT','GEN','1','1'), ('OT','GEN','1','3'), ('OT','PSA','3','0'), ('OT','PSA','3','1'), \
                        ('OT','DAN','1','21'),
                        ('NT','MAT','3','5'), ('NT','JDE','1','4'), ('NT','REV','22','21'), \
                        ('DC','BAR','1','1'), ('DC','MA1','1','1'), ('DC','MA2','1','1',), ):
        (t, b, c, v) = reference
        if t=='OT' and len(SwBible)==27: continue # Don't bother with OT references if it's only a NT
        if t=='NT' and len(SwBible)==39: continue # Don't bother with NT references if it's only a OT
        if t=='DC' and len(SwBible)<=66: continue # Don't bother with DC references if it's too small
        svk = VerseReferences.SimpleVerseKey( b, c, v )
        #print( svk, SwBible.getVerseDataList( reference ) )
        shortText = svk.getShortText()
        try:
            verseText = SwBible.getVerseText( svk )
            fullVerseText = SwBible.getVerseText( svk, fullTextFlag=True )
        except KeyError:
            verseText = fullVerseText = "Verse not available!"
        if BibleOrgSysGlobals.verbosityLevel > 1:
            if BibleOrgSysGlobals.debugFlag: print()
            print( reference, shortText, verseText )
            if BibleOrgSysGlobals.debugFlag: print( '  {}'.format( fullVerseText ) )

    if BibleOrgSysGlobals.debugFlag and debuggingThisModule:
        BBB = 'JN1'
        if BBB in SwBible:
            for entryKey in SwBible.books[BBB]._CVIndex:
                print( BBB, entryKey, SwBible.books[BBB]._CVIndex.getEntries( entryKey ) )
# end of testSwB


def demo():
    """
    Main program to handle command line parameters and then run what they want.
    """
    if BibleOrgSysGlobals.verbosityLevel > 0: print( ProgNameVersion )


    testFolder = '/home/robert/.sword/'
    # Matigsalug_Test module
    #testFolder = '/mnt/Data/Websites/Freely-Given.org/Software/BibleDropBox/Matigsalug.USFM.Demo/Sword_(from OSIS_Crosswire_Python)/CompressedSwordModule'


    if 0: # demo the file checking code -- first with the whole folder and then with only one folder
        result1 = SwordBibleFileCheck( testFolder )
        if BibleOrgSysGlobals.verbosityLevel > 1: print( "Sword TestA1", result1 )
        result2 = SwordBibleFileCheck( testFolder, autoLoad=True )
        if BibleOrgSysGlobals.verbosityLevel > 1: print( "Sword TestA2", result2 )
        result3 = SwordBibleFileCheck( testFolder, autoLoadBooks=True )
        if BibleOrgSysGlobals.verbosityLevel > 1: print( "Sword TestA3", result3 )


    if 0: # specified module
        singleModule = 'LEB' # Can be blank if a specific test folder is given containing only one module
        if BibleOrgSysGlobals.verbosityLevel > 1: print( "\nSword B/ Trying {}".format( singleModule ) )
        #myTestFolder = os.path.join( testFolder, singleModule+'/' )
        #testFilepath = os.path.join( testFolder, singleModule+'/', singleModule+'_utf8.txt' )
        testSwB( testFolder, singleModule )

    if 1: # specified modules
        good = ('KJV','WEB','KJVA','YLT','ASV','LEB','OEB',)
        nonEnglish = (  )
        bad = ( )
        for j, testFilename in enumerate( good ): # Choose one of the above: good, nonEnglish, bad
            if BibleOrgSysGlobals.verbosityLevel > 1: print( "\nSword D{}/ Trying {}".format( j+1, testFilename ) )
            #myTestFolder = os.path.join( testFolder, testFilename+'/' )
            #testFilepath = os.path.join( testFolder, testFilename+'/', testFilename+'_utf8.txt' )
            testSwB( testFolder, testFilename )


    if 0: # all discovered modules in the test folder
        foundFolders, foundFiles = [], []
        for something in os.listdir( testFolder ):
            somepath = os.path.join( testFolder, something )
            if os.path.isdir( somepath ): foundFolders.append( something )
            elif os.path.isfile( somepath ): foundFiles.append( something )

        if BibleOrgSysGlobals.maxProcesses > 1: # Get our subprocesses ready and waiting for work
            if BibleOrgSysGlobals.verbosityLevel > 1: print( "\nTrying all {} discovered modules...".format( len(foundFolders) ) )
            parameters = [(testFolder,folderName) for folderName in sorted(foundFolders)]
            with multiprocessing.Pool( processes=BibleOrgSysGlobals.maxProcesses ) as pool: # start worker processes
                results = pool.map( testSwB, parameters ) # have the pool do our loads
                assert( len(results) == len(parameters) ) # Results (all None) are actually irrelevant to us here
        else: # Just single threaded
            for j, someFolder in enumerate( sorted( foundFolders ) ):
                if BibleOrgSysGlobals.verbosityLevel > 1: print( "\nSword E{}/ Trying {}".format( j+1, someFolder ) )
                #myTestFolder = os.path.join( testFolder, someFolder+'/' )
                testSwB( testFolder, someFolder )
# end of demo


if __name__ == '__main__':
    # Configure basic set-up
    parser = BibleOrgSysGlobals.setup( ProgName, ProgVersion )
    BibleOrgSysGlobals.addStandardOptionsAndProcess( parser, exportAvailable=True )

    multiprocessing.freeze_support() # Multiprocessing support for frozen Windows executables

    demo()

    BibleOrgSysGlobals.closedown( ProgName, ProgVersion )
# end of SwordBible.py