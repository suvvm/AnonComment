from contextlib import contextmanager
from textfilter import DFAFilter
import mysql.connector
import mysql.connector.pooling
import pandas as pd
import numpy as np
import re


# 数据库配置
config = {
    'host': 'localhost',
    'user': 'root',
    'passwd': 'guyu980324',
    'database': 'acdb',
    'charset': 'utf8'
}

# 建立数据库连接池
try:
    connections_pool = mysql.connector.pooling.MySQLConnectionPool(pool_name='my_conn_pool',
                                                                   pool_size=5,
                                                                   **config)
except Exception as ex:
    print('创建数据库连接池发生异常：\n{}'.format(ex))
    connections_pool = None

# 创建一个DFA敏感词过滤器
dfa_filter = DFAFilter()
dfa_filter.parse('keywords')


@contextmanager
def open_mysql(db_conf: dict, conns_pool: 'connections_pool'):
    """
    数据库上下文管理器
    :param db_conf: 字典类型，数据库连接配置
    :param conns_pool: 数据库连接池
    :return: 返回数据库对象
    """
    try:
        if conns_pool:
            # 如果数据库连接池非空，从数据库连接池中获取连接
            flag = 1
            conn = conns_pool.get_connection()
            if conn:
                yield conn
        else:
            # 否则创建一个新连接
            flag = 2
            conn = mysql.connector.connect(**db_conf)
            if conn:
                yield conn
    except Exception as e:
        print('发生异常：\n{}'.format(e))
        if flag == 1:
            try:
                # 如果是在获取连接池中的连接时发生异常，尝试创建新连接
                conn = mysql.connector.connect(**db_conf)
                if conn:
                    yield conn
            except Exception as e:
                print('获取数据库连接池的连接发生异常，创建连接又发生异常：\n{}'.format(e))
    finally:
        conn.close()


def init():
    """
    初始化数据库，建表操作
    :return: None
    """
    with open_mysql(config, connections_pool) as db:
        cursor = db.cursor()
        cursor.execute('SHOW TABLES')
        if not cursor.fetchall():
            # 建表SQL语句
            create_teachers_table_sql = "CREATE TABLE teachers (" \
                                        "t_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY," \
                                        "name VARCHAR(10) NOT NULL," \
                                        "pinyin VARCHAR(50) NOT NULL," \
                                        "college VARCHAR(20) NOT NULL," \
                                        "institute VARCHAR(30) NOT NULL," \
                                        "department VARCHAR(20) NOT NULL," \
                                        "degree VARCHAR(15)," \
                                        "title VARCHAR(10)," \
                                        "courses VARCHAR(255) NOT NULL," \
                                        "tot_score BIGINT NOT NULL DEFAULT 0," \
                                        "num BIGINT NOT NULL DEFAULT 0," \
                                        "score FLOAT NOT NULL DEFAULT 0," \
                                        "yes BIGINT NOT NULL DEFAULT 0," \
                                        "percent FLOAT DEFAULT NULL);"

            insert_teachers_table_sql = "INSERT INTO teachers (name, pinyin, degree, title, courses, " \
                                        "college, institute, department) " \
                                        "VALUES " \
                                        "(%s, %s, %s, %s, %s, %s, %s, %s);"

            create_comments_table_sql = "CREATE TABLE comments (" \
                                        "c_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY," \
                                        "t_id INT NOT NULL," \
                                        "content VARCHAR(300) NOT NULL," \
                                        "support INT NOT NULL DEFAULT 0," \
                                        "post_time DATE NOT NULL);"

            create_user_comments_table_sql = "CREATE TABLE user_comments (" \
                                             "id INT NOT NULL AUTO_INCREMENT PRIMARY KEY," \
                                             "openid VARCHAR(50) NOT NULL," \
                                             "t_id INT NOT NULL," \
                                             "score INT NOT NULL," \
                                             "yes INT NOT NULL," \
                                             "content VARCHAR(300) NOT NULL," \
                                             "c_id INT DEFAULT NULL);"

            create_user_supports_table_sql = "CREATE TABLE user_supports (" \
                                             "id INT NOT NULL AUTO_INCREMENT PRIMARY KEY," \
                                             "openid VARCHAR(50) NOT NULL," \
                                             "c_id INT NOT NULL," \
                                             "t_id INT NOT NULL);"
            try:
                cursor.execute(create_teachers_table_sql)
                cursor.execute(create_comments_table_sql)
                cursor.execute(create_user_comments_table_sql)
                cursor.execute(create_user_supports_table_sql)

                # 获取老师信息并插入表
                with open('./app/static/data/data.csv', 'rb') as f:
                    pd_data = pd.read_csv(f, header=None, encoding='gb18030', keep_default_na=False)

                data = np.array(pd_data)
                insert_data = list((tuple(i) for i in data))
                cursor.execute('USE acdb')
                cursor.executemany(insert_teachers_table_sql, insert_data)
                db.commit()
            except Exception as e:
                print('发生异常：\n{}'.format(e))
                # 发生异常则回滚
                db.rollback()


def get_all_comments_num():
    """
    查询全站所有评论数
    :return: 字符串类型，评论数
    """
    with open_mysql(config, connections_pool) as db:
        cursor = db.cursor()
        count = None
        sql = "SELECT COUNT(*) FROM comments"
        try:
            cursor.execute(sql)
            count = cursor.fetchone()
        except Exception as e:
            print('发生异常：\n{}'.format(e))
            # 发生异常则回滚
            db.rollback()

    if count:
        return str(count[0])
    else:
        return None


def select_all_teachers():
    """
    查询所有老师
    :return: 字典类型，key值表示部门，value值是一个列表，每个元素是一位老师的信息
    """
    with open_mysql(config, connections_pool) as db:
        cursor = db.cursor()
        table = {}
        select_sql = "SELECT t_id, name, pinyin, department FROM teachers;"
        try:
            cursor.execute(select_sql)
            # 获取所有老师的信息列表
            teachers = cursor.fetchall()
            # 生成所有老师的信息字典
            for teacher in teachers:
                if teacher[3] not in table.keys():
                    table[teacher[3]] = []
                table[teacher[3]].append(str(teacher[0]) + ' ' + teacher[1] + ' ' + teacher[2])
        except Exception as e:
            print('发生异常：\n{}'.format(e))
            # 发生异常则回滚
            db.rollback()

    return table


def select_all_teachers_for_search():
    """
    查询所有老师信息，为模糊搜索提供数据
    :return: 字典类型，key：中文姓名+拼音+id，如'张三zhangsan1'
                      value: 列表信息，[t_id, name, pinyin, score, department, degree, title]
    """
    with open_mysql(config, connections_pool) as db:
        cursor = db.cursor()
        info = {}
        select_sql = "SELECT t_id, name, pinyin, score, department, degree, title  FROM teachers;"
        try:
            cursor.execute(select_sql)
            teachers = cursor.fetchall()
            # 生成所有老师的信息字典
            for teacher in teachers:
                key = teacher[1] + teacher[2] + str(teacher[0])
                teacher = list(teacher)
                # 分数保留两位小数
                teacher[3] = round(teacher[3], 2)
                info[key] = teacher
        except Exception as e:
            print('发生异常：\n{}'.format(e))
            # 发生异常则回滚
            db.rollback()

    return info


def select_teacher_info(teacher: str):
    """
    查询某位老师的信息和评论
    :param teacher: 字符串类型，组成为教师id+姓名拼音（没有+号，如1zhangsan）
                    用于数据库查找该老师的信息
    :return: 列表类型，返回列表，该老师的全部信息
    """
    with open_mysql(config, connections_pool) as db:
        cursor = db.cursor()
        info = []
        # 将teacher中的t_id利用正则表达式分离出来，以便进行查询
        t_id = int(re.match(r'([0-9]+)([a-z]+)', teacher).group(1))
        select_sql = "SELECT * FROM teachers WHERE t_id={}".format(t_id)
        try:
            cursor.execute(select_sql)
            # 将教师的信息列表化
            info = list(cursor.fetchone())
            if info[11]:
                # 如果有评分，将教师得分和点名率保留两位小数
                info[11] = round(info[11], 2)
                info[13] = round(info[13] * 100.0, 2)
        except Exception as e:
            print('发生异常：\n{}'.format(e))
            # 发生异常则回滚
            db.rollback()

    return info


def select_comments(t_id: int):
    """
    根据教师id查询对该老师的所有评论
    :param t_id: 整型，教师id
    :return: comments和count
             comments：列表类型，每个元素为一条评论的所有信息，包括内容，时间，点赞数等
             count：元组类型，只有一个元素，为某位老师的所有评论数
    """
    with open_mysql(config, connections_pool) as db:
        cursor = db.cursor()
        comments = []
        count = ()
        try:
            # 默认按照点赞数排序获取评论
            select_sql = "SELECT * FROM comments WHERE t_id={} ORDER BY support DESC, c_id DESC".format(t_id)
            cursor.execute(select_sql)
            comments = cursor.fetchall()
            # 获取该老师评论总个数
            select_sql = "SELECT COUNT(*) FROM comments WHERE t_id={}".format(t_id)
            cursor.execute(select_sql)
            count = cursor.fetchone()
        except Exception as e:
            print('发生异常：\n{}'.format(e))
            # 发生异常则回滚
            db.rollback()

    return comments, count


def select_for_ranking():
    """
    获取所有老师的列表，为教师排行榜提供数据
    :return: 列表类型，老师列表
    """
    with open_mysql(config, connections_pool) as db:
        cursor = db.cursor()
        teachers = []
        select_sql = "SELECT t_id, name, pinyin, tot_score, num, score FROM teachers"
        try:
            cursor.execute(select_sql)
            teachers = cursor.fetchall()
        except Exception as e:
            print('发生异常：\n{}'.format(e))
            # 发生异常则回滚
            db.rollback()

    return teachers


def is_commented(openid: str, t_id: int):
    """
    根据openid和t_id查询用户评价表中是否有记录，没有则说明该用户未对该老师评价，
    否则说明评价过，返回用户评价信息
    :param openid: 字符串类型，用户标识
    :param t_id: 整型，老师id
    :return: 如果存在评价则返回评价列表，否则返回None
    """
    with open_mysql(config, connections_pool) as db:
        cursor = db.cursor()
        res = []
        select_sql = "SELECT * FROM user_comments WHERE openid='{}' AND t_id={};".format(openid, t_id)
        try:
            cursor.execute(select_sql)
            res = cursor.fetchone()
        except Exception as e:
            print('发生异常：\n{}'.format(e))
            # 发生异常则回滚
            db.rollback()

    if res:
        return list(res)
    else:
        return None


def get_like_list(openid: str, t_id: int):
    """
    根据openid和t_id查询用户对该老师的点赞评论，返回点赞的c_id列表
    :param openid: 字符串类型，用户的唯一标识
    :param t_id: 整型，老师id
    :return: 列表类型，每个元素是一个c_id
    """
    with open_mysql(config, connections_pool) as db:
        cursor = db.cursor()
        like_list = []
        sql = "SELECT c_id FROM user_supports WHERE openid='{}' AND t_id={}".format(openid,
                                                                                    t_id)
        try:
            cursor.execute(sql)
            like_list = cursor.fetchall()
            like_list = list(map(lambda x: x[0], like_list))
        except Exception as e:
            print('发生异常：\n{}'.format(e))
            # 发生异常则回滚
            db.rollback()

    return like_list


def insert_comment(t_id: int, score: int, whether: int, comment: str, submit_date: str):
    """
    更新老师信息，插入一条新的评论到评论表
    :param t_id: 整型，教师id
    :param score: 整型，评论的分数
    :param whether: 整型，是否点名
    :param comment: 字符串类型，评论内容
    :param submit_date: 字符串类型，提交时间
    :return: c_id
    """
    with open_mysql(config, connections_pool) as db:
        cursor = db.cursor()
        c_id = None
        try:
            # 更新老师信息
            update_sql = "UPDATE teachers SET tot_score=tot_score+{}, num=num+1, yes=yes+{}," \
                         "score=tot_score/num, percent=yes/num WHERE t_id={};".format(score, whether, t_id)
            cursor.execute(update_sql)
            if comment != "":
                # 如果评论内容不为空插入一条评论
                # 对评论进行敏感词过滤
                comment = dfa_filter.filter(comment)
                # 将评论插入数据库
                insert_sql = "INSERT INTO comments (t_id, content, post_time) VALUES (%s, %s, %s);"
                val = (t_id, comment, submit_date)
                cursor.execute(insert_sql, val)
                # 获取c_id
                cursor.execute("SELECT LAST_INSERT_ID();")
                c_id = cursor.fetchone()[0]
            db.commit()
        except Exception as e:
            print('发生异常：\n{}'.format(e))
            # 发生异常则回滚
            db.rollback()

    return c_id


def insert_user_comment(openid: str, t_id: int, score: int, whether: int,
                        comment: str, c_id: 'int or None'):
    """
    插入新记录到用户评价表，标记用户评价了该老师
    :param openid: 字符串类型，用户唯一标识
    :param t_id: 整型，评论教师的id
    :param score: 整型，评分
    :param whether: 整型，是否点名
    :param comment: 字符串类型，评论内容
    :param c_id: 整型，评论id
    :return: None
    """
    with open_mysql(config, connections_pool) as db:
        cursor = db.cursor()
        insert_sql = "INSERT INTO user_comments (openid, t_id, score, yes, content, c_id) VALUES (%s, %s, %s, %s, %s, %s)"
        # 对评论进行敏感词过滤
        comment = dfa_filter.filter(comment)
        val = (openid, t_id, score, whether, comment, c_id)
        try:
            cursor.execute(insert_sql, val)
            db.commit()
        except Exception as e:
            print('发生异常：\n{}'.format(e))
            # 发生异常则回滚
            db.rollback()


def update_user_comment(teacher: str, openid: str, score: int, whether: int,
                        comment: str, submit_date: str):
    """
    用户更新自己对某位老师的评价
    :param teacher: 字符串类型，为评论老师的URL路径，如/1zhangsan
    :param openid: 字符串类型，当前用户的唯一标识
    :param score: 整型，更新后的评分
    :param whether: 整型，更新后的点名情况
    :param comment: 字符串类型，更新后的评论
    :param submit_date: 字符串类型，更新后的提交日期
    :return: None
    """
    with open_mysql(config, connections_pool) as db:
        cursor = db.cursor()
        try:
            # 根据URL的path部分获取t_id
            t_id = int(re.match(r'/([0-9]+)([a-z]+)', teacher).group(1))
            # 获取用户以前对老师的评价（评分，是否点名，评论，评论的id）
            old_comment = is_commented(openid, t_id)
            old_score = old_comment[3]
            old_whether = old_comment[4]
            c_id = old_comment[6]
            # 对评论进行敏感词过滤
            comment = dfa_filter.filter(comment)
            # 更新教师信息
            sql = "UPDATE teachers SET tot_score=tot_score-{}+{}, yes=yes-{}+{}," \
                  "score=tot_score/num, percent=yes/num WHERE t_id={};".format(old_score, score,
                                                                               old_whether, whether,
                                                                               t_id)
            cursor.execute(sql)
            # 更新用户评价表
            sql = "UPDATE user_comments SET score={}, yes={}, content='{}'" \
                  "WHERE openid='{}' AND t_id={};".format(score, whether, comment, openid, t_id)
            cursor.execute(sql)
            # 更新评论表
            # 原来没评论，现在有评论
            if not c_id and comment != "":
                sql = "INSERT INTO comments (t_id, content, post_time) VALUES (%s, %s, %s);"
                val = (t_id, comment, submit_date)
                cursor.execute(sql, val)
                # 获取c_id
                cursor.execute("SELECT LAST_INSERT_ID();")
                c_id = cursor.fetchone()[0]
                # 更新用户评论表的c_id
                sql = "UPDATE user_comments SET c_id={} WHERE openid='{}' AND t_id={};".format(c_id,
                                                                                               openid,
                                                                                               t_id)
                cursor.execute(sql)
            # 原来有评论，现在也有评论
            elif c_id and comment != "":
                sql = "UPDATE comments SET content='{}' WHERE c_id={};".format(comment, c_id)
                cursor.execute(sql)
            # 原来有评论，现在无评论
            elif c_id and comment == "":
                sql = "DELETE FROM comments WHERE c_id={}".format(c_id)
                cursor.execute(sql)
                sql = "DELETE FROM user_supports WHERE c_id={}".format(c_id)
                cursor.execute(sql)
                sql = "UPDATE user_comments SET c_id=NULL WHERE openid='{}' AND t_id={};".format(openid,
                                                                                                 t_id)
                cursor.execute(sql)

            db.commit()
        except Exception as e:
            print('发生异常：\n{}'.format(e))
            # 发生异常则回滚
            db.rollback()


def update_user_support(openid: str, t_id: int, c_id: int, click: int):
    """
    单条修改点赞记录
    :param openid: 字符串类型，用户唯一标识字符串
    :param t_id: 整型，用户点赞评论对应的老师id
    :param c_id: 整型，点赞的评论id
    :param click: 整型，点赞1或取消点赞0
    :return: None
    """
    with open_mysql(config, connections_pool) as db:
        cursor = db.cursor()
        try:
            if click:
                # 更新用户点赞表
                sql = "INSERT INTO user_supports (openid, c_id, t_id) VALUES (%s, %s, %s)"
                val = (openid, c_id, t_id)
                cursor.execute(sql, val)
                # 更新评论表中support字段
                sql = "UPDATE comments SET support=support+1 WHERE c_id={}".format(c_id)
                cursor.execute(sql)
            else:
                # 更新用户点赞表
                sql = "DELETE FROM user_supports WHERE openid='{}' AND c_id={}".format(openid, c_id)
                cursor.execute(sql)
                # 更新评论表中support字段
                sql = "UPDATE comments SET support=support-1 WHERE c_id={}".format(c_id)
                cursor.execute(sql)

            db.commit()
        except Exception as e:
            print('发生异常：\n{}'.format(e))
            # 发生异常则回滚
            db.rollback()


# 初始化数据库
init()
