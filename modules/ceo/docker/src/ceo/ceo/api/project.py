import os, logging, json, datetime, zipfile, shutil, csv, time
import xml.etree.ElementTree as ET

from flask import Response, session, request, redirect, url_for, jsonify, render_template, send_file, abort
from flask_cors import cross_origin

from .. import app
from .. import mongo

from ..common.utils import import_sepal_auth, requires_auth, propertyFileToDict, allowed_file, generate_id, listToCSVRowString

from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

PROJECT_TYPE_CEP = 'CEP'
PROJECT_TYPE_TRAINING_DATA = 'TRAINING-DATA'

@app.route('/api/project/<id>', methods=['GET'])
@cross_origin(origins=app.config['CO_ORIGINS'])
@import_sepal_auth
@requires_auth
def projectById(id=None):
    project = mongo.db.projects.find_one({'id': id}, {'_id': False})
    if not project:
        abort(404)
    return jsonify(project), 200

@app.route('/api/project', methods=['GET'])
@cross_origin(origins=app.config['CO_ORIGINS'])
@import_sepal_auth
@requires_auth
def projects():
    projects = []
    if session.get('is_admin'):
        projects = mongo.db.projects.find({}, {'_id': False})
    else:
        projects = mongo.db.projects.find({'username': session.get('username')}, {'_id': False})
    return jsonify(list(projects)), 200

@app.route('/api/project/<id>/file', methods=['GET'])
@cross_origin(origins=app.config['CO_ORIGINS'])
@import_sepal_auth
@requires_auth
def projectFileById(id=None):
    project = mongo.db.projects.find_one({'id': id}, {'_id': False})
    filename = project['filename']
    name, ext = os.path.splitext(filename)
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], name, filename), mimetype='text/xml', attachment_filename=filename, as_attachment=True)

@app.route('/api/project', methods=['POST'])
@cross_origin(origins=app.config['CO_ORIGINS'])
@import_sepal_auth
@requires_auth
def projectAdd():
    # retrieve project data
    username = session.get('username')
    print request.form
    name = request.form.get('name')
    radius = request.form.get('radius', type=int)
    overlays = getLayersFromRequest(request)
    projectType = request.form.get('projectType')
    # validation
    if not name or not radius or not projectType:
        return 'KO', 400
    # define basic project
    project = {
        'name': name,
        'type': projectType,
        'username': username,
        'radius': radius,
        'upload_datetime': datetime.datetime.utcnow(),
        'overlays': overlays
    }
    if projectType == PROJECT_TYPE_CEP:
        # check if the post request has the file part
        if 'file' not in request.files:
            print('No file part')
            return 'KO', 400
        file = request.files['file']
        # if user does not select file, browser also submit a empty part without filename
        if file.filename == '':
            print('No selected file')
            return 'KO', 400
        # if the file has the allowed extension
        if file and allowed_file(file.filename, app.config['ALLOWED_EXTENSIONS']):
            result = saveFileFromRequest(file)
            # update project data
            project.update({
                'id': generate_id(result[0]),
                'filename': result[0],
                'plots': result[1],
                'codeLists': result[2]
            })
    elif projectType == PROJECT_TYPE_TRAINING_DATA:
        project.update({
            'id': generate_id(name),
            'codeLists': getCodeListsFromRequest(request)
        })
    mongo.db.projects.insert(project)
    return redirect(app.config['BASE'])

@app.route('/api/project/<id>', methods=['PUT'])
@cross_origin(origins=app.config['CO_ORIGINS'])
@import_sepal_auth
@requires_auth
def projectUpdate(id=None):
    project = mongo.db.projects.find_one({'id': id}, {'_id': False})
    if not project:
        return 'Error!', 404
    if session.get('is_admin') or project['username'] != session.get('username'):
        return 'Forbidden!', 403
    # retrieve project data
    name = request.form.get('name')
    radius = request.form.get('radius', type=int)
    overlays = getLayersFromRequest(request)
    # validation
    if not name or not radius:
        return 'KO', 400
    # update the project
    project.update({
        'name': name,
        'radius': radius,
        'overlays': overlays,
        'update_datetime': datetime.datetime.utcnow()
    })
    projectType = project['type']
    if projectType == PROJECT_TYPE_TRAINING_DATA:
        project.update({
            'codeLists': getCodeListsFromRequest(request)
        })
    mongo.db.projects.update({'id': id}, {'$set': project}, upsert=False)
    return 'OK', 200

@app.route('/api/project/<id>', methods=['PATCH'])
@cross_origin(origins=app.config['CO_ORIGINS'])
@import_sepal_auth
@requires_auth
def projectChange(id=None):
    project = mongo.db.projects.find_one({'id': id}, {'_id': False})
    if not project:
        return 'Error!', 404
    if session.get('is_admin') or project['username'] != session.get('username'):
        return 'Forbidden!', 403
    # retrieve project data
    plots = request.json.get('plots')
    print plots
    # update the project
    projectType = project['type']
    if projectType == PROJECT_TYPE_TRAINING_DATA:
        project.update({
            'plots': plots
        })
    mongo.db.projects.update({'id': id}, {'$set': project}, upsert=False)
    return 'OK', 200

@app.route('/api/project/<id>', methods=['DELETE'])
@cross_origin(origins=app.config['CO_ORIGINS'])
@import_sepal_auth
@requires_auth
def projectRemove(id=None):
    project = mongo.db.projects.find_one({'id': id}, {'_id': False})
    if not project:
        return 'Error!', 404
    if session.get('is_admin') or project['username'] != session.get('username'):
        return 'Forbidden!', 403
    mongo.db.projects.delete_many({'id': id})
    mongo.db.records.delete_many({'project_id': id})
    if project['type'] == PROJECT_TYPE_CEP:
        filename = project['filename']
        if os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        name, ext = os.path.splitext(filename)
        if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], name)):
            shutil.rmtree(os.path.join(app.config['UPLOAD_FOLDER'], name))
    return 'OK', 200

@app.route("/api/project/<id>/export", methods=['GET'])
@cross_origin(origins=app.config['CO_ORIGINS'])
@import_sepal_auth
@requires_auth
def projectExportCSV(id=None):
    #
    project = mongo.db.projects.find_one({'id': id}, {'_id': False})
    username = session.get('username')
    records = mongo.db.records.find({'project_id': id, 'username': username}, {'_id': False})
    filename = project['filename'] + '.csv'
    #
    codeListNames = []
    for codeList in project['codeLists']:
        codeListNames.append(codeList['name'])
    #
    csvHeaderData = ['YCoordinate', 'XCoordinate'] + codeListNames
    csvString = listToCSVRowString(csvHeaderData)
    #
    for record in records:
        csvRowData = []
        csvRowData.append(record.get('plot').get('YCoordinate'))
        csvRowData.append(record.get('plot').get('XCoordinate'))
        values = json.loads(record['value'])
        for codeListName in codeListNames:
            value = values.get(codeListName, '')
            csvRowData.append(value)
        csvString += listToCSVRowString(csvRowData)
    #
    return Response(csvString, mimetype="text/csv", headers={"Content-disposition": "attachment; filename=" + filename})

def saveFileFromRequest(file):
    # save the file
    filename = secure_filename(file.filename)
    name, ext = os.path.splitext(filename)
    uniqueName = name + '--' + str(int(time.time()))
    uniqueFilename =  uniqueName + ext
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], uniqueFilename))
    # extract the files
    extractDir = os.path.join(app.config['UPLOAD_FOLDER'], uniqueName)
    if not os.path.exists(extractDir):
        os.mkdir(extractDir)
        zip_ref = zipfile.ZipFile(os.path.join(app.config['UPLOAD_FOLDER'], uniqueFilename), 'r')
        zip_ref.extractall(extractDir)
        zip_ref.close()
    # codeLists
    codeLists = []
    if os.path.isfile(os.path.join(extractDir, 'placemark.idm.xml')):
        ns = {
            'of': 'http://www.openforis.org/idml/3.0'
        }
        tree = ET.parse(os.path.join(extractDir, 'placemark.idm.xml'))
        lists = tree.findall('of:codeLists/of:list', ns)
        disallowedNames = ('id', 'confidence')
        for lst in lists:
            codeList = {
                'id': lst.attrib.get('id'),
                'name': lst.attrib.get('name'),
                'items': []
            }
            if codeList['name'] not in disallowedNames:
                items = lst.findall('of:items/of:item', ns)
                if len(items) > 0:
                    for item in items:
                        codeList.get('items').append({
                            'code': item.find('of:code', ns).text,
                            'label': item.find('of:label', ns).text
                        })
                    codeLists.append(codeList)
    # properties
    properties = propertyFileToDict(os.path.join(extractDir, 'project_definition.properties'))
    property = properties.get('csv', 'test_plots.ced')
    head, tail = os.path.split(property)
    # plots
    plots = []
    if os.path.isfile(os.path.join(extractDir, tail)):
        with open(os.path.join(extractDir, tail), 'rb') as csvfile:
            csvreader = csv.reader(csvfile, delimiter=',', quotechar='"')
            next(csvreader, None)
            for row in csvreader:
                plots.append({
                    'id': row[0],
                    'YCoordinate': row[1],
                    'XCoordinate': row[2]
                })
    return (uniqueFilename, plots, codeLists)

def getLayersFromRequest(request):
    overlays = []
    layerType = request.form.getlist('layerType[]')
    layerName = request.form.getlist('layerName[]')
    # gee
    collectionName = request.form.getlist('collectionName[]')
    dateFrom = request.form.getlist('dateFrom[]')
    dateTo = request.form.getlist('dateTo[]')
    Min = request.form.getlist('min[]')
    Max = request.form.getlist('max[]')
    band1 = request.form.getlist('band1[]')
    band2 = request.form.getlist('band2[]')
    band3 = request.form.getlist('band3[]')
    # digitalglobe
    mapID = request.form.getlist('mapID[]')
    # gibs
    imageryLayer = request.form.getlist('imageryLayer[]')
    date = request.form.getlist('date[]')
    #
    i1 = i2 = i3 = -1
    for i in range(0, len(layerType)):
        overlay = None
        if layerType[i] == 'gee-gateway':
            i1 += 1
            overlay = {
                'collectionName': collectionName[i1],
                'dateFrom': dateFrom[i1],
                'dateTo': dateTo[i1],
                'min': Min[i1],
                'max': Max[i1],
                'band1': band1[i1],
                'band2': band2[i1],
                'band3': band3[i1]
            }
        elif layerType[i] == 'digitalglobe':
            i2 += 1
            overlay = {
                'mapID': mapID[i2]
            }
        elif layerType[i] == 'gibs':
            i3 += 1
            overlay = {
                'imageryLayer': imageryLayer[i3],
                'date': date[i3]
            }
        if overlay:
            overlay['layerName'] = layerName[i]
            overlay['type'] = layerType[i]
            overlays.append(overlay)
    return overlays

def getCodeListsFromRequest(request):
    codeLists = []
    codeListUniqueID = request.form.getlist('codeListUniqueID[]')
    codeListID = request.form.getlist('codeListID[]')
    codeListName = request.form.getlist('codeListName[]')
    for i, uniqueID in enumerate(codeListUniqueID):
        codeList = {
            'id': codeListID[i],
            'name': codeListName[i],
            'items': []
        }
        codeListCode = request.form.getlist(uniqueID + '-codeListCode[]')
        codeListLabel = request.form.getlist(uniqueID + '-codeListLabel[]')
        for k in range(0, len(codeListCode)):
            codeList['items'].append({
                'code': codeListCode[k],
                'label': codeListLabel[k]
            })
        codeLists.append(codeList)
    return codeLists
