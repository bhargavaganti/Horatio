# coding=utf-8
import udatetime
from app import db
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.plugins.auth.models import Groups, Group
from app.plugins.tasks.routes import tasks_page
from app.plugins.Horatio.forms import CreateCase, EditCase, SaveCase
from app.plugins.Horatio.globals import AVAILABLE_CHOICES
from app.plugins.Horatio.models import Cases, Detection, Indicator,Indicator_Type
from app.plugins.analysis.routes import get_upload_file_hash
from app.plugins.analysis.file.upload import allowed_file
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from re import split

cases = Blueprint('cases', __name__, template_folder='templates')


@tasks_page.route('/cases', methods=['GET'])
@login_required
def cases_plugin_route():
    """the tasks function returns the plugin framework for the yara_plugin default task view"""
    # TODO show current cases in the database
    page = request.args.get('page', 1, type=int)
    case_list = Cases.query.all()
    case_dict = {}
    for item in case_list:
        item_dict = {"id": item.id, "subject": item.subject,
                     "description": item.description, "status": item.case_status}
        case_dict[str(item.id)] = item_dict

    return render_template('cases.html', title='Cases Plugin', page=page, case_list=case_list, table_dict=case_dict)


@tasks_page.route('/create', methods=['GET', 'POST'])
@login_required
def create_case_route():
    """Create case default view."""
    group_info = Groups.query.all()
    if request.method == 'POST':
        form = CreateCase(request.form)
        form.detection_method.choices = AVAILABLE_CHOICES
        file_hash = None
        if form.validate():
            try:
                file = request.files['file']
            except KeyError:
                file = None
            if file and allowed_file(file.filename):
                secure_filename(file.filename)
                file_hash = get_upload_file_hash(file)
            detection_method_selection = None
            for items in AVAILABLE_CHOICES:
                if items[0] == form.detection_method.data[0]:
                    detection_method_selection = items
            new_case = Cases(description=form.description.data, subject=form.subject.data,
                             created_by=current_user.id, case_status="New Issue",
                             detection_method=detection_method_selection[1], group_access=form.group_access.data[0],
                             created_time_stamp=udatetime.utcnow(), modify_time_stamp=udatetime.utcnow(),
                             attached_files=file_hash)
            db.session.add(new_case)
            db.session.commit()
            delim = '(?:\s*[,;])?\s*'
            domains = split(delim, form.malicious_domains.data)
            ips = split(delim, form.malicious_ips.data)
            md5s = split(delim, form.malicious_md5s.data)
            submit_indicator(new_case.id, domains, Indicator_Type.query.filter_by(name="domains").all()[0].indicator_type_id)
            submit_indicator(new_case.id, ips, Indicator_Type.query.filter_by(name="ips").all()[0].indicator_type_id)
            submit_indicator(new_case.id, md5s, Indicator_Type.query.filter_by(name="md5s").all()[0].indicator_type_id)

            flash("The case has been created.")
            return redirect(url_for('tasks.cases_plugin_route'))
    form = CreateCase(request.form)
    return render_template('create_case.html', title='Create Case', form=form, groups=group_info,
                           detection_method=AVAILABLE_CHOICES)

def submit_indicator(caseID, values, indicator_type):
    for item in values:

        new_indicator = Indicator(case_id=caseID, type_id=indicator_type, value=item)
        db.session.add(new_indicator)
    db.session.commit()



@tasks_page.route('/edit', methods=['GET', 'POST'])
@login_required
def edit_case_route():
    """Edit case view."""
    group_info = Groups.query.all()
    submitted_case_id = request.args.get("id")
    group_ids = Group.query.filter_by(username_id=current_user.id).all()
    user_groups = []
    for user_group in group_ids:
        user_groups.append(user_group.groups_id)
    case = Cases.query.filter_by(id=submitted_case_id)
    case = case.filter(or_(Cases.id==submitted_case_id, Cases.group_access.in_(user_groups))).first()
    if request.method == 'POST':
        if case:
            form = EditCase(request.form)
            if form.validate_on_submit():
                case.subject = request.form["subject"]
                case.description = request.form["description"]
                case.case_notes = request.form["case_notes"]
                case.case_rules = request.form["case_rules"]
                db.session.commit()
        return cases_plugin_route()
    if request.method == "GET":
        if case:
            form = EditCase(case)
            table_dict = {"id": case.id, "subject": case.subject, "description": case.description,
                          "case_notes": case.case_notes, "case_rules": case.case_rules}
            return render_template('edit_case.html', title='Edit Case', form=form, groups=group_info,
                                   detection_method=AVAILABLE_CHOICES, table_dict=table_dict)
        else:
            return cases_plugin_route()
