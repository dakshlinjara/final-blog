from crypt import methods

from flask import Flask, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm
from forms import RegisterForm
from forms import LoginForm
from forms import CommentForm
import psycopg2

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)



##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://final_blogs_user:7w8KC3zMLv4KVMCPiRz6K3nb9HipdH0v@dpg-ct719n3qf0us738b6d20-a.oregon-postgres.render.com/final_blogs'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)



login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  # Redirect to login page if not authenticated

@login_manager.unauthorized_handler
def unauthorized():
    # Instead of redirecting to login, raise a 403 error
    return "Forbidden: You do not have access to this resource.", 403

@app.context_processor
def inject_user():
    return {'logged_in': current_user.is_authenticated,'id': current_user.id if current_user.is_authenticated else None,'author': current_user.name if current_user.is_authenticated else None}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Comments(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(300), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # ForeignKey to User
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))  # ForeignKey to BlogPost

    # Relationships
    author = db.relationship('User', back_populates='comments')  # Many-to-one to User
    post = db.relationship('BlogPost', back_populates='comments', cascade="all, delete")  # Many-to-one to BlogPost


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(1000), nullable=False)

    # One-to-many relationship to Comments
    comments = db.relationship('Comments', back_populates='author')


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(250), nullable=False)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # One-to-many relationship to Comments
    comments = db.relationship('Comments', back_populates='post')




@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register',methods=["GET","POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data
        email_check = User.query.filter_by(email=email).first()
        password = form.password.data
        hash_pass = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
        name = form.name.data
        if email_check is not None:
            flash("email already exists.please login", "error")  # Flash success message
            return redirect(url_for("login"))
        else:
            new_user = User(email=email,password=hash_pass,name=name)
            db.session.add(new_user)
            db.session.commit()
            user = User.query.filter_by(email=email).first()
            login_user(user)
            return redirect(url_for("get_all_posts"))

    return render_template("register.html",form=form)


@app.route('/login',methods=["GET","POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('get_all_posts'))
        else:
            if user is None:
                flash("Email Does not Exist.", "error")  # Flash error only if login failed
            else:
                flash("Wrong Password ", "error")  # Flash error only if login failed
            return render_template("login.html",form=form)  # Re-render the login page with error
    return render_template("login.html", form=form)




@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>",methods=["GET","POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    form = CommentForm()
    # Filter comments to only include those associated with the current post
    comments = Comments.query.filter_by(post_id=post_id).all()

    if form.validate_on_submit():
        text = form.text.data
        new_comment = Comments(text=text, user_id=current_user.id, post_id=post_id)
        db.session.add(new_comment)
        db.session.commit()
        # Redirect to the same page to reload comments
        return redirect(url_for("show_post", post_id=post_id))

    return render_template("post.html", post=requested_post, form=form, comments=comments if comments else None)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post",methods=["GET","POST"])
@login_required
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user.name,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>")
@login_required
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@login_required
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))

@app.route("/commentdelete/<comment_id>")
@login_required
def delete_comment(comment_id):
    comment_to_delete = Comments.query.get(comment_id)
    db.session.delete(comment_to_delete)
    db.session.commit()
    return redirect(url_for('show_post', post_id=comment_to_delete.post_id))



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)
    with app.app_context():
        db.create_all()
