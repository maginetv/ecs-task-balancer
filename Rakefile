# To run locally
# AWS_PROFILE=<PROFILE> rake

# Build either a particular lambda or all lambdas
LAMBDA = ENV['LAMBDA']
LAMBDAS = LAMBDA ? [LAMBDA] : FileList['*'].exclude('tmp-*').select {|f| File.directory?(f)}


# Create virtual env to test lambdas
VIRTUALENV_DIR = "tmp-pyenv-lambda"


task :pre_build do
    sh "virtualenv #{VIRTUALENV_DIR}"
    sh "#{VIRTUALENV_DIR}/bin/pip install awscli flake8 nose"# matplotlib"
end


task :test => [:pre_build] do
    sh "#{VIRTUALENV_DIR}/bin/pip install -r requirements.txt;"
    sh "#{VIRTUALENV_DIR}/bin/flake8 --show-source *.py"
    sh "#{VIRTUALENV_DIR}/bin/nosetests -svx tests"
end


task :build do |t|
    sh "rm -rf build; mkdir build; \
        pip install -r requirements.txt -t build; \
        rsync -r --verbose --exclude='*.pyc' ./* build/;
        cd build; zip -r -q build.zip *;"
end


task :cleanup do
    sh "rm -f *.zip"
    sh "rm -rf */build"
    sh "rm -rf #{VIRTUALENV_DIR}"
end


task :default => ["pre_build", "test", "build"]