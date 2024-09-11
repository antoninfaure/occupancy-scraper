from os import environ
from dotenv import load_dotenv
load_dotenv()

DB_USER = environ.get('DB_USER')
DB_PASSWORD = environ.get('DB_PASSWORD')
DB_URL = environ.get('DB_URL')
DB_NAME = environ.get('DB_NAME')
SECRET_KEY = environ.get('SECRET_KEY')

ROOMS_FILTER = [
    'POL.N3.E',
    'POL315.1',
    'PHxx',
    'Max412',
    'STCC - Garden Full',
    'ELG124',
    'EXTRANEF126',
    'CHCIGC'
]

MAP_ROOMS = {
    'CE1': 'CE11',
    'CM4': 'CM14',
    'BC07-08': ['BC07','BC08'],
    'CM3': 'CM13',
    'CE4': 'CE14',
    'CM2': 'CM12',
    'SG1': 'SG1138',
    'SG1 138': 'SG1138',
    'CE6': 'CE16',
    'CM5': 'CM15',
    'CE5': 'CE15',
    'CM1': 'CM11',
    'CE2': 'CE12',
    'CE3': 'CE13',
    'RLC E1 240': 'RLCE1240',
    'STCC - Cloud C': 'STCC78025'
}

MAP_PROMOS = {
    'Bachelor 1': 'BA1',
    'Bachelor 2' : 'BA2',
    'Bachelor 3' : 'BA3',
    'Bachelor 4' : 'BA4',
    'Bachelor 5' : 'BA5',
    'Bachelor 6' : 'BA6',
    'Master 1' : 'MA1',
    'Master 2' : 'MA2',
    'Master 3' : 'MA3',
    'Master 4' : 'MA4',
    'PDM Printemps' : 'PME',
    'PDM Automne' : 'PMH',
}

MAP_PROMOS_LONG = {
    'Bachelor semestre 1': 'BA1',
    'Bachelor semestre 2': 'BA2',
    'Bachelor semestre 3': 'BA3',
    'Bachelor semestre 4': 'BA4',
    'Bachelor semestre 5': 'BA5',
    'Bachelor semestre 5b': 'BA5',
    'Bachelor semestre 6': 'BA6',
    'Bachelor semestre 6b': 'BA6',
    'Master semestre 1': 'MA1',
    'Master semestre 2': 'MA2',
    'Master semestre 3': 'MA3',
    'Master semestre 4': 'MA4',
    'PDM Automne': 'PMH',
    'PDM Printemps': 'PME',
    'Ecole doctorale': 'EDOC',
    'Admission printemps': 'ADME',
    'Admission automne': 'ADMH',
    'Semestre printemps': 'E',
    'Semestre automne': 'H',
    'Projet Master printemps': 'PME',
    'Projet Master automne': 'PMH',
    
}

MAP_SECTIONS = {
    'Génie mécanique': 'GM',
    'Mécanique': 'GM',
    'Mineur en Génie mécanique': 'GM',
    'Architecture': 'AR',
    'Mineur en Design intégré architecture et durabilité': 'AR',
    'Chimie et génie chimique': 'CGC',
    'Génie civil': 'GC',
    'Génie électrique et électronique': 'EL',
    'Génie électrique': 'EL',
    'Mineur en Energie': 'EL',
    'Informatique': 'IN',
    'Informatique et communications': 'IN',
    'Mineur en Informatique': 'IN',
    'Data and Internet of Things minor': 'SC',
    'Cyber security minor': 'SC',
    'Mineur en Science et ingénierie quantiques': 'SIQ',
    'Mineur en Imaging': 'MT',
    'Ingénierie des sciences du vivant': 'SV',
    'Mathématiques': 'MA',
    'Microtechnique': 'MT',
    'Physique': 'PH',
    'Auditeurs en ligne': 'AUDIT',
    'Science et génie des matériaux': 'MX',
    "Sciences et ingénierie de l'environnement": 'SIE',
    'Systèmes de communication': 'SC',
    'Chimie': 'CGC',
    'Mineur en Ingénierie pour la durabilité': 'SIE',
    'Génie chimique': 'CGC',
    'Chimie moléculaire et biologique': 'CGC',
    'Humanités digitales': 'HD',
    'Data Science': 'SC',
    'Energy Science and Technology': 'EL',
    'Management, technologie et entrepreneuriat': 'MTE',
    'Management technologie et entrepreneuriat': 'MTE',
    'Management de la technologie': 'MTE',
    'Mineur en Management technologie et entrepreneuriat': 'MTE',
    'Mineur en Systems Engineering': 'MTE',
    'Génie chimique et biotechnologie': 'CGC',
    'Génie nucléaire': 'PH',
    'Informatique - Cybersecurity': 'IN',
    'Ingénierie financière': 'IF',
    'Mineur en Ingénierie financière': 'IF',
    'Ingénierie physique': 'PH',
    'Physique - master': 'PH',
    'Management durable et technologie': 'MTE',
    'Mathématiques - master': 'MA',
    'Statistique': 'MA',
    'Neuro-X': 'NX',
    'Neurosciences': 'NX',
    'Passerelle HES - CGC': 'CGC',
    'Passerelle HES - EL': 'EL',
    'Passerelle HES - SIE': 'SIE',
    'Passerelle HES - MT': 'MT',
    'Passerelle HES - AR': 'AR',
    'Passerelle HES - GC': 'GC',
    'Passerelle HES - GM': 'GM',
    'Passerelle HES - IC': 'IN',
    'Projeter ensemble ENAC': 'AR',
    'Microsystèmes et microélectronique': 'MT',
    'Mineur en Neuroprosthétiques': 'NX',
    'Manufacturing': 'GM',
    'Finance': 'IF',
    'Approches moléculaires du vivant': 'SV',
    'Mineur en Computational biology': 'SV',
    'Mineur en Physique des systèmes vivants': 'SV',
    'Biologie computationnelle et quantitative': 'SV',
    'Biotechnologie et génie biologique': 'SV',
    'Mineur en Neurosciences computationnelles': 'NX',
    'Ingénierie mathématique': 'MA',
    'Micro- and Nanotechnologies for Integrated Systems': 'EL',
    'Robotique': 'MT',
    'Science et ingénierie computationnelles': 'MA',
    'Science et ingénierie quantiques': 'SIQ',
    'Systèmes de communication - master': 'SC',
    'Programme Sciences humaines et sociales': 'SHS',
    'Mineur en Technologies biomédicales': 'SV',
    'Mineur en Neuro-X': 'NX',
    'Robotique contrôle et systèmes intelligents': 'MT',
    'UNIL - Collège des sciences': 'UNIL',
    'Mineur en Science et ingénierie computationnelles': 'MA',
    'Mineur en Systèmes de communication': 'SC',
    'Mineur en Développement territorial et urbanisme': 'AR',
    'Mineur en Territoires en transformation et climat': 'SIE',
    'Mobilité AR': 'AR',
    'Photonique': 'MT',
    'Photonics minor': 'MT',
    'UNIL - Autres facultés': 'UNIL',
    'UNIL - HEC': 'UNIL',
    'UNIL - Géosciences': 'UNIL',
    'UNIL - Sciences forensiques': 'UNIL',
    "Science et technologie de l'énergie": 'EL',
    'Mineur en Technologies spatiales': 'EL',
    'Génie civil et environnement': 'GC',
    'Mineur en Data science': 'SC',
    'Mineur en Humanités digitales médias et société': 'HD',
    'Mineur en Génie civil': 'GC',
    'Joint EPFL - ETH Zurich Doctoral Program in the Learning Sciences': 'ETH',
    'Mineur en Biotechnologie': 'SV',
    'Cours généraux et externes EDOC': 'EDOC',
    'Mineur en Biocomputing': 'SV',
    'Mineur en Ingénierie des Sciences du Vivant': 'SV',
    'Architecture et sciences de la ville': 'AR',
    'Energie': 'EL',
    'Mineur en Biocomputing': 'SV'
 }

MAP_SEMESTERS = {
    'BA1': 'fall',
    'BA2': 'spring',
    'BA3': 'fall',
    'BA4': 'spring',
    'BA5': 'fall',
    'BA6': 'spring',
    'MA1': 'fall',
    'MA2': 'spring',
    'MA3': 'fall',
    'MA4': 'spring',
    'PMH': 'fall',
    'PME': 'spring',
}

MAP_SEMESTERS_LONG = {
    'Bachelor semestre 1': 'fall',
    'Bachelor semestre 2': 'spring',
    'Bachelor semestre 3': 'fall',
    'Bachelor semestre 4': 'spring',
    'Bachelor semestre 5': 'fall',
    'Bachelor semestre 5b': 'fall',
    'Bachelor semestre 6': 'spring',
    'Bachelor semestre 6b': 'spring',
    'Master semestre 1': 'fall',
    'Master semestre 2': 'spring',
    'Master semestre 3': 'fall',
    'Master semestre 4': 'spring',
    'PDM Automne': 'fall',
    'Projet Master automne': 'fall',
    'PDM Printemps': 'spring',
    'Projet Master printemps': 'spring',
    'Ecole doctorale': 'year',
    'Admission printemps': 'spring',
    'Admission automne': 'fall',
    'Semestre printemps': 'spring',
    'Semestre automne': 'fall',
    'Joint EPFL - ETH Zurich Doctoral Program in the Learning Sciences': 'year',
    'Cours généraux et externes EDOC': 'year',

}
