from app import app
from flask import render_template, redirect, request, session
from form import CommentForm, SearchForm
from ranking import ranking
from fuzzy_search import get_suggestions
import acdb


# table字典的key值表示部门，value值是一个列表，每个元素是一位老师的信息
table = {}
# 每个元素为一条评论的所有信息，包括内容，时间，点赞数等
comments = []
# 只有一个元素，为某位老师的所有评论数
count = ()
# 模糊搜索时需要的老师数据信息
fuzzy_info = {}


@app.route('/')
@app.route('/index')
def index():
    """
    匿名评教首页
    :return: 渲染模板
    """
    # 实例化一个搜索表单
    search_form = SearchForm()
    return render_template('index.html',
                           title='匿名评教',
                           search_form=search_form)


@app.route('/teachers')
def show_all_teachers():
    """
    显示所有老师界面
    1. 按照学院部门显示
    2. 按照排行榜显示
    :return: 渲染模板
    """
    # 使用全局教师table信息
    global table
    # 如果为空就调用数据库接口获取
    if not table:
        table = acdb.select_all_teachers()
    # 实例化一个搜索表单
    search_form = SearchForm()
    return render_template('teachers.html',
                           title='所有老师',
                           table=table,
                           search_form=search_form)


@app.route('/<teacher>', methods=['GET', 'POST'])
def show_teacher(teacher: str):
    """
    显示每一位老师的界面，包括老师信息和相关评价
    :param teacher: 字符串类型，组成为教师id+姓名拼音（没有+号），用于数据库查找该老师的评论
    :return: 渲染模板
    """
    # 使用全局变量
    global comments, count
    # 通过传入的参数查询数据库老师的信息
    info = acdb.select_teacher_info(teacher)
    # 获取该老师的评论和个数
    comments, count = acdb.select_comments(info[0])
    # 实例化一个评论提交表单
    form = CommentForm()
    # 实例化一个搜索表单
    search_form = SearchForm()
    # 评论表单提交验证
    if form.validate_on_submit():
        # 验证成功，获取表单数据
        score = form.score.data
        whether_call_roll = form.whether_call_roll.data
        comment = form.comment.data
        submit_date = form.submit_date.data
        # 更新老师信息，插入一条评论
        acdb.update_comment(info[0], score, whether_call_roll, comment, submit_date)
        return redirect('/'+teacher)

    return render_template('teacher.html',
                           title=info[1]+'-'+info[3]+info[4],
                           info=info,
                           form=form,
                           count=count[0],
                           comments=comments,
                           search_form=search_form)


@app.route('/rank', methods=['GET', 'POST'])
def rank_by():
    """
    该函数处理每位老师评论的显示方式，按照最热评论和最新评论显示
    接收前端ajax请求进行局部更新页面
    :return: 渲染模板片段
    """
    # 获取前端请求
    way = int(request.form.get('way'))
    if not way:
        # 为0按照最热评论显示
        return render_template('show_comments.html',
                               count=count[0],
                               comments=comments)
    else:
        # 为1按照最新评论显示
        # 以c_id排序
        return render_template('show_comments.html',
                               count=count[0],
                               comments=sorted(comments, key=lambda t: t[0], reverse=True))


@app.route('/total', methods=['GET'])
def get_all_comments_num():
    """
    首页获取全站评论条数，ajax轮询请求，执行该函数
    :return: 字符串类型，评论数
    """
    return acdb.get_all_comments_num()


@app.route('/ways', methods=['GET', 'POST'])
def rank_or_departments():
    """
    显示所有老师界面，按照部门显示或按照排行榜显示
    接收ajax请求，执行操作
    :return: 渲染模板片段
    """
    # 获取ajax请求数据
    ways = int(request.form.get('ways'))
    if not ways:
        # 为0按照部门显示
        return render_template('show_by_departments.html',
                               table=table)
    else:
        # 为1按照排行榜显示
        # 获取最新排行榜
        rank = ranking()
        return render_template('show_by_rank.html', rank=rank[:30])


@app.route('/search', methods=['GET', 'POST'])
def search():
    """
    模糊搜索后端处理
    :return: 渲染模板
    """
    global fuzzy_info
    # 获取老师的数据，通过ajax请求的关键词从中进行匹配
    if not fuzzy_info:
        fuzzy_info = acdb.select_all_teachers_for_search()
    # 获取ajax请求数据
    tip = request.form.get('tip')
    # 实例化搜索表单
    search_form = SearchForm()
    suggestions = []
    flag = 0
    if tip:
        # tip为1说明是为提示框提供数据发起的请求
        keyword = request.form.get('keyword')
        if keyword != '':
            # 当传入的keyword不为空才进行匹配
            suggestions, _ = get_suggestions(keyword, fuzzy_info)
            return render_template('tip_list.html', suggestions=suggestions[:8])
    else:
        # 点击搜索框按钮
        if search_form.validate_on_submit():
            keyword = search_form.search_bar.data
            session['keyword'] = keyword + ' '
            suggestions, flag = get_suggestions(keyword, fuzzy_info)
            redirect('/search')

        return render_template('search_results.html',
                               title=session.get('keyword') + '搜索结果',
                               keyword=session.get('keyword'),
                               results_num=len(suggestions),
                               search_form=search_form,
                               suggestions=suggestions,
                               flag=flag)


# ------------------------以下作为尝试第三方登陆的测试-------------------------------