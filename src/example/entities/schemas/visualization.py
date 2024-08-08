from marshmallow import Schema
from marshmallow.fields import String, List, Nested, Integer

# from controllers import schemas
# from biodm.schemas import K8sinstanceSchema
from .project import ProjectSchema


class VisualizationSchema(Schema):
    id = Integer()
    name = String()

    # datasets = List(Nested(DatasetSchema))


# class Visualization(Base):
#     id = Column(Integer, primary_key=True)
#     name = Column(String)

#     id_project:      Mapped[int] = Column(ForeignKey("PROJECT.id"))
#     id_k8sinstance:  Mapped[int] = Column(ForeignKey("K8SINSTANCE.id"))

#     # k8sinstance: Mapped["K8sinstance"] = relationship(foreign_keys=[id_k8sinstance], lazy="select")
#     project: Mapped["Project"]    = relationship(back_populates="visualizations", lazy="select")
