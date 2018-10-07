from distutils.core import setup

#This is a list of files to install, and where
#(relative to the 'root' dir, where setup.py is)
#You could be more specific.
files = ["things/*"]

setup(
    name = "tumblr_collector",
    version = "1.0",
    keywords = ("tumblr", "collector"),
    description = "tumblr collector tools",
    long_description = """tumblr collector tools""",
    license = "MIT Licence",

    url = "https://github.com/webignorant/tumblr_collector",
    author = "webignorant",
    author_email = "webignorant@gmail.com",

    #Name the folder where your packages live:
    #(If you have other packages (dirs) or modules (py files) then
    #put them into the package directory - they will be found
    #recursively.)
    packages = [],
    include_package_data = True,
    platforms = "any",
    install_requires = [
        "requests>=2.10.0",
        "six>=1.11.0",
        "PySocks>=1.5.6",
        "beautifulsoup4>=4.6.3"
    ],

    #'package' package must contain files (see list above)
    #I called the package 'package' thus cleverly confusing the whole issue...
    #This dict maps the package name =to=> directories
    #It says, package *needs* these files.
    package_data = {'package' : files },
    #'runner' is in the root.
    scripts = ["runner"],
    #
    #This next part it for the Cheese Shop, look a little down the page.
    #classifiers = []
)