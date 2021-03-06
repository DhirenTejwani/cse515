from lxml import etree
from os import listdir, path
from os.path import isfile
from util import timed
from database import Database
from multiprocessing import Pool

################################################################
####                    GENERIC LOADER                      ####
################################################################

class GenericReader():

    def __init__(self):
        # self.loaded = Queue(maxsize=0)
        pass

    ##
    # Method to load a file of this type.
    # NOTE: this should append to self.loaded.
    def load_file(self, file, index=None):
        raise NotImplementedError

    ##
    #
    def load_files(self, files, indexes=None):
        return_val = {}
        if indexes:
            for index, file in zip(indexes, files):
                out = self.load_file(file, index)
                return_val[index] = out
        else:
            for file in files:
                out = self.load_file(file)
                return_val[file] = out
        return return_val

    ##
    #
    def load_folder(self, folder):
        files = self.__get_files__(folder)
        return self.load_files(files)

    ##
    # Method to load a folder of folder.
    def load_directory(self, directory):
        return_val = []
        for folder in listdir(directory):
            out = self.load_folder(directory + '/' + folder)
            return_val.append(out)
        return return_val
    
    ##
    #
    def __get_files__(self, folder):
        #for file in listdir(folder):
        #    if isfile(folder + '/' + file:
        #
        return [folder + '/' + file for file in listdir(folder) if isfile(folder + '/' + file) and not file.startswith('.')]


################################################################
####               TEXT DESCRIPTION LOADER                  ####
################################################################

# NOTE -  The textual descriptions can be found in the folder Dataset/desctext
#   Each of them are structured as followed.
#   ID  "Text Term That Appeared" TF IDF TF-IDF
#   The ID will be the id of an image, user, or other depending on the
#       file.
#
# Indended to be used by calling load_files. Returns dictionary with keys
#   'photos', 'users', and 'poi'. Each key points to a pandas dataframe with
#   the description information for those items.
class DescriptionReader(GenericReader):

    def __init__(self):
        self.seen = []

    def load_file(self, file, index):
        if not isfile(file):
            raise OSError('Could not parse description file ' + str(file) + ' as it doesn\'t exist')
        
        # Strategy - create matrix representation with lists and then put into a new pandas dataframe.
        table = {}
        with open(file) as f:
            for i, line in enumerate(f):
                # Tokenize
                tokens = line.split(' ')
                if '\n' in tokens:
                    tokens.remove('\n')
                # Find out how many tokens make up the ID
                for k, token in enumerate(tokens):
                    if '"' in token:
                        # This is our first term. Return our index to get the id.
                        j = k
                        break
                an_id = ' '.join(tokens[0: j])
                # convert to an int if possible
                try:
                    an_id = int(an_id)
                except:
                    pass

                table[an_id] = {}

                for k in range(j,len(tokens), 4):
                    four_tuple = tokens[k : k + 4]
                    term, tf, idf, tfidf = four_tuple
                    term = term.replace('\"', '')
                    # if 'User' in file and i == 784 and term[0] == 'x':
                    #     print(four_tuple)
                    table[an_id][term] = idf # At TAs Recommendation I chose one of these models arbitrarily.

        return table



################################################################
####                    LOCATION DATA                       ####
################################################################

##
# Meant to be used by calling load_files(name_file, corr_file)
# Returns a dataframe with location information.
class LocationReader(GenericReader): # GenericReader inheritance - don't forget it!

    def load_file(self, file, index=None):
        self.load_files(file, 'poiNameCorrespondences.txt')

    ##
    # Loads the location file using location and name_correlation files.
    def load_files(self, name_file, corr_file):
        name_corr = self.load_name_corr(corr_file)
        return self.load_locations(name_file, name_corr)

    ##
    # Create dictionary of title > Location
    def load_locations(self, file, name_correlation):

        if not isfile(file):
            raise OSError('The location data could not be loaded as the provided file was invalid: ' + str(file))
        if not type(name_correlation) is dict:
            raise TypeError('Name correlation was not of the appropriate dictionary type: ' + str(type(name_correlation)))
        
        tree = etree.parse(file)
        root = tree.getroot()
        rows = list()

        for location in root:
            # Load all data from branch.
            locationid = int(location.find('number').text)
            title = location.find('title').text
            name = name_correlation[title]
            latitude = float(location.find('latitude').text)
            longitude = float(location.find('longitude').text)
            wiki = location.find('wiki').text
            rows.append([locationid, title, name, latitude, longitude, wiki])
        return rows

    ##
    # Load title > name correlations
    def load_name_corr(self, file):
        if not isfile(file):
            raise OSError('The name correlation dictionary could not be created as the provided parameter was not a vaild file: ' + str(file))

        name_correlation = {}
        with open(file) as f:
            for line in f:
                name, title = line.strip('\n').split('\t')
                name_correlation[title] = name

        return name_correlation


################################################################
####                   VISUAL DESC LOADER                   ####
################################################################

class VisualDescriptionReader(GenericReader):

    def load_file(self, file):
        # Just accrue list of csv files to load into the database.
        #   Little wasteful, but it allows the existing code to create
        #   the list desired.
        return file


################################################################
####                    Load All Data                       ####
################################################################
class Loader():

    @staticmethod
    @timed
    def make_database(folder):

        db = Database()
        # p = P ool(processes=3)
        
        # Load location data for associating the id's to the names.
        loc_files = (folder + '/devset_topics.xml', folder + '/poiNameCorrespondences.txt')
        location_dict = LocationReader().load_files(*loc_files)
        db.add_locations(location_dict)
        
        # Load text description data.
        text_files = [folder + '/desctxt/devset_textTermsPerPOI.txt',
                      folder + '/desctxt/devset_textTermsPerImage.txt',
                      folder + '/desctxt/devset_textTermsPerUser.txt']
        types = ['poi', 'photo', 'user']
        descs = DescriptionReader().load_files(text_files,types)
        db.add_txt_descriptors(descs)
        
        # Load visual description data.
        files = VisualDescriptionReader().load_folder(folder + '/descvis/')
        db.add_visual_descriptors(files)

        return db