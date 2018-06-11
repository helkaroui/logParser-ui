from flask import Flask , render_template, g, redirect, url_for, abort,flash, current_app , request, jsonify
from init_db import LocalDb as DB
from algorithm.IPLoM.IPLoM import runIPLoM as IPLoM
from algorithm.IPLoM.IPLoM import splitIPLoM
from algorithm.IPLoM.statistics import statistics
from algorithm.KPI_analyser.KPI import KPI
import os
import json
import pandas as pd
import shutil



app = Flask(__name__)
config = {}
config["transform_chars"] = [("\("," ( "),("\)"," ) "),("=","= "),(","," , "),("sql-thread-","sql-thread- ")]
config["DATABASE"] ='db/database.db'
config["SCHEMA"] ='db/schema.sql'
myDB = DB(config)



@app.route('/')
def index():
   return render_template('index.html')


@app.route('/log')
def logs():
    return str(myDB.query_db('SELECT * FROM logs',one=True))


@app.route('/logs')
def get_logs():
    return render_template('logs.html',logList=myDB.query_db('SELECT * FROM logs'))

@app.route('/logs/add', methods=['POST'])
def logs_add():
    myDB.add_entry('''insert into logs (Processus, Type,Path) values (?,?,?)''',args=[request.form['name'],"name",request.form['path']])
    return redirect(url_for('get_logs'))

@app.route('/log/delete/<log_id>')
def logs_delete(log_id):
    myDB.add_entry('delete from logs where id=?',args=[log_id])
    return redirect(url_for('get_logs'))

@app.route('/log/<log_id>')
def logs_show(log_id):
    stat = myDB.query_db('SELECT params FROM statistics where log_id=?',args=[log_id],one=True)
    reports = myDB.query_db('SELECT * FROM reports WHERE log_id=?',args=[log_id])
    profiles_set = myDB.query_db('SELECT * FROM profiles')
    return render_template('log.html',param={'log_id':log_id,'statistics':stat,'reports':reports},profiles=profiles_set)

@app.route('/log/<log_id>/analyse')
def logs_analyse(log_id):
    stat=statistics(path=myDB.query_db('SELECT Path FROM logs Where id=?',args=[log_id],one=True)['Path'])
    myDB.add_entry('''insert into statistics (log_id, params) values (?,?)''',args=[log_id,str(stat.nbrLines())])
    return redirect(url_for('logs_show',log_id=log_id))


@app.route('/reports')
def reports():
    report = myDB.query_db('SELECT * FROM reports')
    return 'welcome %s' % str(report)


@app.route('/reports/add1', methods=['POST'])
def reports_add1():
    profile = myDB.query_db('SELECT * FROM profiles WHERE id=?', args=[request.form.get('profile', None)], one=True)
    params = format_req(json.loads(profile["params"]))
    log = myDB.query_db('SELECT * FROM logs WHERE id=?', args=[request.form.get('log_id', None)], one=True)
    params["path"] = log['Path']
    params["savePath"] = './reports/'
    params["log_id"] = request.form.get('log_id', None)
    params["transform_chars"] = config["transform_chars"]
    print(params)
    clusters = IPLoM(params)
    report_id = myDB.insert_db('''insert into reports (clusters,log_id, params,length) values (?,?,?,?)''',args=[json.dumps(clusters),request.form.get('log_id', None),json.dumps(request.form),str(len(clusters["report"]))])
    return redirect(url_for('reports_show', report_id=report_id))


@app.route('/reports/add', methods=['POST'])
def reports_add():
    profile = myDB.query_db('SELECT * FROM profiles WHERE id=?', args=[request.form.get('profile', None)], one=True)
    params = format_req(json.loads(profile["params"]))
    log = myDB.query_db('SELECT * FROM logs WHERE id=?', args=[request.form.get('log_id', None)], one=True)
    params["path"] = log['Path']
    params["saveFileName"] = log['Processus']
    params["savePath"] = './reports/'
    params["log_id"] = request.form.get('log_id', None)
    params["transform_chars"] = config["transform_chars"]
    clusters = IPLoM(params)
    report_id = myDB.insert_db('''insert into reports (clusters,log_id, params,length) values (?,?,?,?)''',args=[json.dumps(clusters),request.form.get('log_id', None),json.dumps(request.form),str(len(clusters["report"]))])
    return redirect(url_for('reports_show', report_id=report_id))

@app.route('/reports/split', methods=['POST'])
def reports_split():
    report_id = request.form.get('reportId', None)
    report = myDB.query_db('SELECT * FROM reports WHERE id=?',args=[report_id],one=True)
    report['clusters'] = json.loads(str(report['clusters']))
    report['params'] = json.loads(str(report['params']))
    profile = myDB.query_db('SELECT * FROM profiles WHERE id=?', args=[report['params']["profile"]], one=True)
    params = format_req(json.loads(profile["params"]))
    clusters = splitIPLoM(params, report['clusters'], request.form.get('eventId', None))

    myDB.insert_db('''UPDATE reports SET clusters = ? , length = ? WHERE id=?''',
                   args=[json.dumps(clusters), str(len(clusters["report"])), report_id])

    return redirect(url_for('reports_show', report_id=report_id))


def format_req(req):
    expressions = {'Timestamp':r"(([0-9]+)-([0-9]+)-([0-9]+) ([0-9]+):([0-9]+):([0-9]+).([0-9]+))" ,
                   'IP':'(?:\d{1,3}\.){3}\d{1,3}',
                   'uuid4':'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})',
                   'uuid4_flat': '([0-9a-fA-F]{32})'}
    #meta chars : . ^ $ * + ? { } [ ] \ | ( )
    chars = {'(':'\(',')':'\)','[':'\[',']':'\]','|':'\|',"{":"\{","}":"\}",".":"\.","\\":"\\","?":"\?","+":"\+","*":"\*","$":"\$","^":"\^"}
    args = {}
    args["remove_expression"] = req.get('remove_expression', None) if req.get('remove_expression_cbx', None) else None
    args["line_starter"] = [str(req.get('line_starter', None))] #if req.get('line_starter_cbx', None) else None
    args["remove_col"] = req.get('remove_col', None) if req.get('remove_col_cbx', None) else None
    args["remove_chars"] = req.get('remove_chars', None) if req.get('remove_chars_cbx', None) else None
    args["use_pst"] = float(req.get('use_pst', None)) if req.get('use_pst_cbx', None) else 0.0
    args["first_line"] = int(req.get('first_line', None)) if req.get('first_line', None) else 1
    args["last_line"] = int(req.get('last_line', None))
    args["maxEventLen"] = int(req.get('maxEventLen', None)) if req.get('maxEventLen', None) else 0.0
    args["step2Support"] = float(req.get('step2Support', None)) if req.get('step2Support', None) else 0.0
    args["CT"] = float(req.get('CT', None)) if req.get('CT', None) else 0.0
    args["lowerBound"] = float(req.get('lowerBound', None)) if req.get('lowerBound', None) else 0.0
    args["upperBound"] = float(req.get('upperBound', None)) if req.get('upperBound', None) else 0.0

    if args["remove_col"]:
        args["remove_col"] = map(int,args["remove_col"].split(','))

    if(args["remove_expression"]):
        args["remove_expression"] = [expressions[re] if(re in expressions) else re for re in args["remove_expression"].split(',') ]

    if(args["remove_chars"]):
        args["remove_chars"] = [chars[re] if(re in chars) else re for re in args["remove_chars"].split(',') ]

    if args["line_starter"]:
        args["line_starter"] = [expressions[re] if(re in expressions) else re for re in args["line_starter"]][0]
    return args


@app.route('/reports/delete',methods=['POST'])
def reports_delete():
    myDB.add_entry('delete from reports where id=?',args=[request.form['report_id']])
    return redirect(url_for('logs_show',log_id=request.form['log_id']))

@app.route('/reports/<report_id>')
def reports_show(report_id):
    report = myDB.query_db('SELECT * FROM reports WHERE id=?',args=[report_id],one=True)
    report['clusters'] = json.loads(str(report['clusters']))
    report['params'] = json.loads(str(report['params']))
    KPI = possibleKPIs(report['clusters']['report'])
    #tosave = [[r['eventId'], tagtotag(r['tags'])] for r in report['clusters']['report']]
    #tosave = pd.DataFrame(tosave)
    #tosave.to_csv('moeka_n.csv',header=False,index=False)
    return render_template('report.html',report=report,
                           clusters=report['clusters']['report'],
                           stars=report['clusters']['stars'],
                           KPI=KPI)

def tagtotag(tags):
    return [t['tag'] for t in tags]


def possibleKPIs(cl):
    possibleKpi = []
    for evt in cl:
        for tag in evt['tags']:
            if tag['kpi_score'] > 0:
                possibleKpi.append(tag['tag'])
    return list(set(possibleKpi))



from plotly.offline import download_plotlyjs, init_notebook_mode, plot, iplot
from plotly.offline.offline import _plot_html

@app.route('/reports/<report_id>/makeKPI')
def kpi_make(report_id):
    report = myDB.query_db('SELECT * FROM reports WHERE id=?', args=[report_id], one=True)
    report['clusters'] = json.loads(str(report['clusters']))
    full_path = report['clusters']['full_path']
    dir = full_path.replace('.csv', '')
    if os.path.exists(dir):
        shutil.rmtree(dir)
    os.makedirs(dir)
    KPI(report['clusters']['report'], full_path, full_path.replace('.csv', ''))
    return jsonify(result=True)


@app.route('/reports/<report_id>/getKPI')
def kpi_get(report_id):
    evt = request.args.get('event', '', type=str)
    kpi = request.args.get('kpi', '', type=str)
    path = request.args.get('path', '', type=str)
    print(path.replace('.csv', '')+"/"+evt+"_"+kpi+".csv")
    KPI = pd.read_csv(path.replace('.csv', '')+"/"+evt+"_"+kpi+".csv")
    KPI = KPI.sort_values(by=['x'])
    return jsonify(result={'title':kpi, 'x':KPI.x.tolist(),'y':KPI.y.tolist()})


@app.route('/profiles')
def profiles():
    profiles_set = myDB.query_db('SELECT * FROM profiles')
    return render_template('profiles.html', profiles_set=profiles_set)

@app.route('/profiles/add',methods=['POST'])
def profiles_add():
    profile_id = myDB.insert_db('''insert into profiles (name, params) values (?,?)''', args=[request.form.get('name', None), "[]"])
    return redirect(url_for('profiles_show', profile_id=profile_id))



@app.route('/profiles/update',methods=['POST'])
def profiles_update():
    print(request.form)
    myDB.insert_db('''UPDATE profiles SET name = ? , params = ? WHERE id=?''', args=[request.form.get('name', None), json.dumps(request.form), request.form["profile_id"]])
    return redirect(url_for('profiles_show', profile_id=request.form["profile_id"]))



@app.route('/profiles/delete/<profile_id>')
def profiles_delete(profile_id):
    myDB.add_entry('delete from profiles where id=?', args=[profile_id])
    return redirect(url_for('profiles'))

@app.route('/profiles/<profile_id>')
def profiles_show(profile_id):
    profile = myDB.query_db('SELECT * FROM profiles WHERE id=?', args=[profile_id], one=True)
    #return str(json.loads(str(profile['params'])))
    return render_template('profile.html', params=json.loads(str(profile['params'])), profile_id=profile_id , name=profile['name'] )


@app.route('/profile_list')
def profile_list():
    profiles_set = myDB.query_db('SELECT * FROM profiles')
    return json.dumps(profiles_set)


@app.route('/echo',methods=['POST'])
def echo():
    return str(request.form)


if __name__ == '__main__':
    app.run(port=8001)
